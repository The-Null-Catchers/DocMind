from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import (
    Conversation,
    Document,
    DocumentTag,
    Flashcard,
    FlashcardDeck,
    Message,
    Note,
    User,
)
from ..schemas import SearchHit, SearchRequest
from ..services.retrieval import RetrievalService

router = APIRouter(prefix="/search", tags=["search"])


class GlobalSearchRequest(BaseModel):
    workspace_id: str
    query: str = Field(min_length=1, max_length=4000)
    mode: str = Field(default="hybrid", pattern="^(keyword|exact|semantic|hybrid)$")
    content_types: list[str] = Field(
        default_factory=lambda: [
            "documents",
            "document_content",
            "conversations",
            "notes",
            "flashcards",
        ],
        max_length=5,
    )
    document_ids: list[str] = Field(default_factory=list, max_length=100)
    folder_id: str | None = None
    mime_types: list[str] = Field(default_factory=list, max_length=50)
    tag_ids: list[str] = Field(default_factory=list, max_length=50)
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = Field(default=30, ge=1, le=100)


def _terms(query: str) -> list[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", query.casefold(), flags=re.UNICODE)


def _lexical_score(query: str, *values: str, exact: bool = False) -> float:
    needle = re.sub(r"\s+", " ", query.casefold()).strip()
    haystack = re.sub(r"\s+", " ", " ".join(values).casefold())
    if not needle:
        return 0.0
    if exact:
        return 1.0 if needle in haystack else 0.0
    terms = set(_terms(needle))
    if not terms:
        return 0.0
    matched = sum(1 for term in terms if term in haystack)
    phrase_bonus = 0.25 if needle in haystack else 0.0
    return min(1.0, matched / len(terms) + phrase_bonus)


def _text_predicates(columns: list, query: str, exact: bool):
    if exact:
        return [column.ilike(f"%{query.strip()}%") for column in columns]
    terms = _terms(query)[:12]
    if not terms:
        return [column.ilike(f"%{query.strip()}%") for column in columns]
    return [
        column.ilike(f"%{term}%")
        for column in columns
        for term in terms
    ]


@router.post("", response_model=list[SearchHit])
async def search(
    payload: SearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SearchHit]:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    hits = await RetrievalService(db).search(
        workspace_id=payload.workspace_id,
        query=payload.query,
        document_ids=payload.document_ids,
        folder_id=payload.folder_id,
        exact_phrase=payload.exact_phrase,
        mode="exact" if payload.exact_phrase else "hybrid",
        limit=payload.limit,
    )
    return [
        SearchHit(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            document_title=h.document_title,
            page_number=h.page_number,
            section_title=h.section_title,
            excerpt=h.text[:700],
            score=h.score,
            semantic_score=h.semantic_score,
            keyword_score=h.keyword_score,
        )
        for h in hits
    ]


@router.post("/global")
async def global_search(
    payload: GlobalSearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    allowed_types = {
        "documents",
        "document_content",
        "conversations",
        "notes",
        "flashcards",
    }
    content_types = [value for value in payload.content_types if value in allowed_types]
    exact = payload.mode == "exact"
    per_type = max(5, min(30, payload.limit))
    results: list[dict] = []

    document_filters = [
        Document.workspace_id == payload.workspace_id,
        Document.deleted_at.is_(None),
    ]
    if payload.document_ids:
        document_filters.append(Document.id.in_(payload.document_ids))
    if payload.folder_id:
        document_filters.append(Document.folder_id == payload.folder_id)
    if payload.mime_types:
        document_filters.append(Document.mime_type.in_(payload.mime_types))
    if payload.tag_ids:
        document_filters.append(
            Document.id.in_(
                select(DocumentTag.document_id).where(
                    DocumentTag.tag_id.in_(payload.tag_ids)
                )
            )
        )
    if payload.created_after:
        document_filters.append(Document.created_at >= payload.created_after)
    if payload.created_before:
        document_filters.append(Document.created_at <= payload.created_before)

    if "documents" in content_types:
        predicates = _text_predicates(
            [Document.title, Document.original_filename],
            payload.query,
            exact,
        )
        documents = db.scalars(
            select(Document)
            .where(*document_filters, or_(*predicates))
            .order_by(Document.updated_at.desc())
            .limit(per_type)
        ).all()
        for document in documents:
            score = _lexical_score(
                payload.query,
                document.title,
                document.original_filename,
                exact=exact,
            )
            results.append(
                {
                    "type": "document",
                    "id": document.id,
                    "title": document.title,
                    "excerpt": document.original_filename,
                    "score": score,
                    "document_id": document.id,
                    "page_number": 1,
                    "chunk_id": None,
                    "updated_at": document.updated_at,
                }
            )

    if "document_content" in content_types:
        hits = await RetrievalService(db).search(
            workspace_id=payload.workspace_id,
            query=payload.query,
            document_ids=payload.document_ids,
            folder_id=payload.folder_id,
            mode=payload.mode,
            mime_types=payload.mime_types,
            tag_ids=payload.tag_ids,
            created_after=payload.created_after,
            created_before=payload.created_before,
            limit=per_type,
        )
        for hit in hits:
            results.append(
                {
                    "type": "document_content",
                    "id": hit.chunk_id,
                    "title": hit.document_title,
                    "excerpt": hit.text[:700],
                    "score": hit.score,
                    "document_id": hit.document_id,
                    "page_number": hit.page_number,
                    "chunk_id": hit.chunk_id,
                    "updated_at": None,
                }
            )

    if "conversations" in content_types:
        predicates = _text_predicates(
            [Conversation.title, Message.content],
            payload.query,
            exact,
        )
        conversation_statement = (
            select(Conversation, Message)
            .join(Message, Message.conversation_id == Conversation.id, isouter=True)
            .where(
                Conversation.workspace_id == payload.workspace_id,
                Conversation.user_id == user.id,
                or_(*predicates),
            )
            .order_by(Conversation.updated_at.desc())
            .limit(per_type * 3)
        )
        if payload.created_after:
            conversation_statement = conversation_statement.where(Conversation.created_at >= payload.created_after)
        if payload.created_before:
            conversation_statement = conversation_statement.where(Conversation.created_at <= payload.created_before)
        seen: set[str] = set()
        for conversation, message in db.execute(conversation_statement).all():
            if conversation.id in seen:
                continue
            seen.add(conversation.id)
            excerpt = message.content[:700] if message and message.content else conversation.title
            results.append(
                {
                    "type": "conversation",
                    "id": conversation.id,
                    "title": conversation.title,
                    "excerpt": excerpt,
                    "score": _lexical_score(
                        payload.query,
                        conversation.title,
                        excerpt,
                        exact=exact,
                    ),
                    "document_id": None,
                    "page_number": None,
                    "chunk_id": None,
                    "updated_at": conversation.updated_at,
                }
            )
            if len(seen) >= per_type:
                break

    if "notes" in content_types:
        predicates = _text_predicates([Note.title, Note.content_markdown], payload.query, exact)
        note_statement = (
            select(Note)
            .where(
                Note.workspace_id == payload.workspace_id,
                Note.user_id == user.id,
                or_(*predicates),
            )
            .order_by(Note.updated_at.desc())
            .limit(per_type)
        )
        if payload.created_after:
            note_statement = note_statement.where(Note.created_at >= payload.created_after)
        if payload.created_before:
            note_statement = note_statement.where(Note.created_at <= payload.created_before)
        for note in db.scalars(note_statement).all():
            results.append(
                {
                    "type": "note",
                    "id": note.id,
                    "title": note.title,
                    "excerpt": note.content_markdown[:700],
                    "score": _lexical_score(
                        payload.query,
                        note.title,
                        note.content_markdown,
                        exact=exact,
                    ),
                    "document_id": None,
                    "page_number": None,
                    "chunk_id": None,
                    "updated_at": note.updated_at,
                }
            )

    if "flashcards" in content_types:
        predicates = _text_predicates(
            [Flashcard.front, Flashcard.back, FlashcardDeck.name],
            payload.query,
            exact,
        )
        flashcard_statement = (
            select(Flashcard, FlashcardDeck)
            .join(FlashcardDeck, FlashcardDeck.id == Flashcard.deck_id)
            .where(
                FlashcardDeck.workspace_id == payload.workspace_id,
                FlashcardDeck.user_id == user.id,
                or_(*predicates),
            )
            .order_by(Flashcard.updated_at.desc())
            .limit(per_type)
        )
        if payload.created_after:
            flashcard_statement = flashcard_statement.where(Flashcard.created_at >= payload.created_after)
        if payload.created_before:
            flashcard_statement = flashcard_statement.where(Flashcard.created_at <= payload.created_before)
        for card, deck in db.execute(flashcard_statement).all():
            results.append(
                {
                    "type": "flashcard",
                    "id": card.id,
                    "title": deck.name,
                    "excerpt": f"{card.front}\n{card.back}"[:700],
                    "score": _lexical_score(
                        payload.query,
                        deck.name,
                        card.front,
                        card.back,
                        exact=exact,
                    ),
                    "document_id": None,
                    "page_number": None,
                    "chunk_id": None,
                    "updated_at": card.updated_at,
                }
            )

    results.sort(
        key=lambda item: (
            float(item["score"] or 0.0),
            str(item["updated_at"] or ""),
        ),
        reverse=True,
    )
    return results[: payload.limit]
