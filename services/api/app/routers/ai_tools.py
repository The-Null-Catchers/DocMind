from __future__ import annotations

import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Document, DocumentChunk, DocumentPage, Flashcard, FlashcardDeck, Note, Quiz, QuizQuestion, User
from ..ai.providers import get_llm_provider
from ..services.extraction import StructuredExtractionService
from ..services.rag import RAGService
from ..services.usage import record_usage

router = APIRouter(tags=["ai-tools"])


class DocumentsRequest(BaseModel):
    workspace_id: str
    document_ids: list[str] = Field(min_length=1, max_length=20)
    language: str = Field(default="auto", pattern="^(auto|en|ar)$")


class SummaryRequest(DocumentsRequest):
    style: str = Field(default="detailed", pattern="^(short|detailed|executive|bullet|study)$")


class CompareRequest(DocumentsRequest):
    focus: str | None = Field(default=None, max_length=2000)


class ExtractionRequest(DocumentsRequest):
    schema_definition: dict


class StudyGenerateRequest(DocumentsRequest):
    count: int = Field(default=10, ge=1, le=50)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class SelectionActionRequest(BaseModel):
    workspace_id: str
    document_id: str
    page_number: int = Field(ge=1)
    selected_text: str = Field(min_length=2, max_length=12000)
    action: str = Field(
        pattern="^(explain|summarize|rewrite|translate|ask|create_flashcard|add_to_notes)$"
    )
    question: str | None = Field(default=None, max_length=2000)
    target_language: str | None = Field(default=None, max_length=40)


class TableAskRequest(BaseModel):
    workspace_id: str
    document_id: str
    page_number: int = Field(ge=1)
    table_index: int = Field(ge=0)
    question: str = Field(min_length=2, max_length=2000)


def _normalize_selection(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = re.sub(r"-\s+(?=\w)", "", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def _selection_page(
    db: Session,
    *,
    workspace_id: str,
    document_id: str,
    page_number: int,
    selected_text: str,
) -> tuple[Document, DocumentPage]:
    document = db.get(Document, document_id)
    if (
        not document
        or document.deleted_at
        or document.workspace_id != workspace_id
    ):
        raise HTTPException(status_code=404, detail="Document not found")
    page = db.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
        )
    )
    if not page:
        raise HTTPException(status_code=404, detail="Document page not found")
    selected = _normalize_selection(selected_text)
    source = _normalize_selection(page.text)
    if not selected or selected not in source:
        raise HTTPException(
            status_code=422,
            detail="Selected text could not be verified against this document page",
        )
    return document, page


async def _selection_generation(payload: SelectionActionRequest) -> tuple[str, str, str]:
    instructions = {
        "explain": "Explain this selection clearly and concisely. Do not introduce unsupported facts.",
        "summarize": "Summarize this selection faithfully and concisely.",
        "rewrite": "Rewrite this selection for clarity while preserving its meaning. Do not add facts.",
        "translate": (
            f"Translate this selection into {payload.target_language or 'English'}. "
            "Preserve names, numbers, and meaning."
        ),
        "ask": payload.question or "Answer what this selection means using only the selected text.",
    }
    llm = get_llm_provider()
    source_context = (
        "[SOURCE C1]\n"
        f"Document: {payload.document_id}\n"
        f"Page: {payload.page_number}\n"
        f"{payload.selected_text}"
    )
    messages = [
        {"role": "system", "content": source_context},
        {"role": "user", "content": instructions[payload.action]},
    ]
    parts: list[str] = []
    async for part in llm.stream(
        system=(
            "Use only the supplied document selection. "
            "Do not invent context that is not present in the source."
        ),
        messages=messages,
    ):
        parts.append(part)
    return "".join(parts).strip(), llm.name, llm.model


@router.post("/ai/selection")
async def selection_action(
    payload: SelectionActionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    document, _page = _selection_page(
        db,
        workspace_id=payload.workspace_id,
        document_id=payload.document_id,
        page_number=payload.page_number,
        selected_text=payload.selected_text,
    )
    citation = {
        "document_id": document.id,
        "page_number": payload.page_number,
        "source_excerpt": payload.selected_text[:1200],
    }

    if payload.action == "create_flashcard":
        require_workspace_role(db, payload.workspace_id, user.id, "editor")
        deck = db.scalar(
            select(FlashcardDeck).where(
                FlashcardDeck.workspace_id == payload.workspace_id,
                FlashcardDeck.user_id == user.id,
                FlashcardDeck.name == "Selection cards",
            )
        )
        if not deck:
            deck = FlashcardDeck(
                workspace_id=payload.workspace_id,
                user_id=user.id,
                name="Selection cards",
                language="ar" if re.search(r"[\u0600-\u06FF]", payload.selected_text) else "en",
            )
            db.add(deck)
            db.flush()
        preview = re.sub(r"\s+", " ", payload.selected_text).strip()
        card = Flashcard(
            deck_id=deck.id,
            front=("اشرح: " if deck.language == "ar" else "Explain: ") + preview[:240],
            back=payload.selected_text,
            source_citations=[citation],
            difficulty="medium",
            tags=["selection"],
        )
        db.add(card)
        db.commit()
        return {
            "kind": "flashcard",
            "deck_id": deck.id,
            "card_id": card.id,
            "citation": citation,
        }

    if payload.action == "add_to_notes":
        require_workspace_role(db, payload.workspace_id, user.id, "editor")
        preview = re.sub(r"\s+", " ", payload.selected_text).strip()
        note = Note(
            workspace_id=payload.workspace_id,
            user_id=user.id,
            title=preview[:80] or "Document selection",
            content_markdown=payload.selected_text,
            source_links=[citation],
        )
        db.add(note)
        db.commit()
        return {
            "kind": "note",
            "note_id": note.id,
            "citation": citation,
        }

    content, provider, model = await _selection_generation(payload)
    record_usage(
        db,
        workspace_id=payload.workspace_id,
        user_id=user.id,
        metric="ai_messages",
        quantity=1,
        provider=provider,
        model=model,
        metadata={
            "feature": "selection_action",
            "action": payload.action,
            "document_id": payload.document_id,
            "page_number": payload.page_number,
        },
    )
    db.commit()
    return {
        "kind": "generation",
        "content": content,
        "provider": provider,
        "model": model,
        "citation": citation,
    }


@router.post("/ai/table")
async def ask_table(
    payload: TableAskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    document = db.get(Document, payload.document_id)
    if (
        not document
        or document.deleted_at
        or document.workspace_id != payload.workspace_id
    ):
        raise HTTPException(status_code=404, detail="Document not found")
    page = db.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == payload.document_id,
            DocumentPage.page_number == payload.page_number,
        )
    )
    if not page:
        raise HTTPException(status_code=404, detail="Document page not found")
    tables = page.metadata_json.get("tables", []) if isinstance(page.metadata_json, dict) else []
    table = next(
        (
            item
            for item in tables
            if isinstance(item, dict) and item.get("table_index") == payload.table_index
        ),
        None,
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    rows = table.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=422, detail="Table has no structured rows")
    rendered_rows = [
        " | ".join(str(cell) for cell in row)
        for row in rows
        if isinstance(row, list)
    ]
    table_text = "\n".join(rendered_rows)[:16000]
    llm = get_llm_provider()
    parts: list[str] = []
    async for part in llm.stream(
        system=(
            "Answer using only the supplied structured document table. "
            "Do not infer facts that are not represented in the table."
        ),
        messages=[
            {
                "role": "system",
                "content": (
                    "[SOURCE TABLE T1]\n"
                    f"Document: {document.title}\n"
                    f"Page: {payload.page_number}\n"
                    f"{table_text}"
                ),
            },
            {"role": "user", "content": payload.question},
        ],
    ):
        parts.append(part)
    record_usage(
        db,
        workspace_id=payload.workspace_id,
        user_id=user.id,
        metric="ai_messages",
        quantity=1,
        provider=llm.name,
        model=llm.model,
        metadata={
            "feature": "table_question",
            "document_id": document.id,
            "page_number": payload.page_number,
            "table_index": payload.table_index,
        },
    )
    db.commit()
    return {
        "content": "".join(parts).strip(),
        "provider": llm.name,
        "model": llm.model,
        "citation": {
            "document_id": document.id,
            "page_number": payload.page_number,
            "table_index": payload.table_index,
            "source_excerpt": table_text[:1200],
        },
    }


@router.post("/summaries/generate")
async def summary(payload: SummaryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    result = await RAGService(db).answer(workspace_id=payload.workspace_id, document_ids=payload.document_ids, question=f"Create a {payload.style} summary of the selected documents. Include the important findings and cite every document-derived claim.")
    return {"content": result.answer, "citations": [c.__dict__ for c in result.citations]}


@router.post("/compare")
async def compare(payload: CompareRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    question = "Compare these documents: identify similarities, differences, contradictions, shared topics, key metrics, and timeline differences."
    if payload.focus:
        question += f" Focus especially on: {payload.focus}."
    result = await RAGService(db).answer(workspace_id=payload.workspace_id, document_ids=payload.document_ids, question=question)
    return {"content": result.answer, "citations": [c.__dict__ for c in result.citations]}


@router.post("/extract")
async def extract(payload: ExtractionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    return await StructuredExtractionService(db).extract(workspace_id=payload.workspace_id, document_ids=payload.document_ids, schema=payload.schema_definition)


@router.post("/flashcards/generate", status_code=201)
def generate_flashcards(payload: StudyGenerateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.workspace_id == payload.workspace_id, DocumentChunk.document_id.in_(payload.document_ids)).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(payload.count)).all()
    deck = FlashcardDeck(workspace_id=payload.workspace_id, user_id=user.id, name="Generated study deck", language="ar" if payload.language == "ar" else "en")
    db.add(deck); db.flush()
    cards=[]
    for chunk in chunks:
        sentence = chunk.text.split(".")[0].strip()[:300] or chunk.text[:300]
        front = ("اشرح: " if payload.language == "ar" else "Explain: ") + sentence
        card = Flashcard(deck_id=deck.id, front=front, back=chunk.text[:900], source_citations=[{"chunk_id": chunk.id, "document_id": chunk.document_id, "page_number": chunk.page_start}], difficulty=payload.difficulty, tags=[])
        db.add(card); cards.append(card)
    db.commit()
    return {"deck_id": deck.id, "count": len(cards)}


@router.post("/quizzes/generate", status_code=201)
def generate_quiz(payload: StudyGenerateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.workspace_id == payload.workspace_id, DocumentChunk.document_id.in_(payload.document_ids)).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(payload.count)).all()
    quiz = Quiz(workspace_id=payload.workspace_id, user_id=user.id, title="Generated document quiz", language="ar" if payload.language == "ar" else "en", difficulty=payload.difficulty)
    db.add(quiz); db.flush()
    count=0
    for chunk in chunks:
        prompt = ("ما الفكرة الرئيسية في هذا الجزء؟" if payload.language == "ar" else "What is the main idea of this source section?")
        question = QuizQuestion(quiz_id=quiz.id, question_type="short_answer", question=prompt, options=[], answer=chunk.text[:350], explanation=chunk.text[:700], source_citations=[{"chunk_id": chunk.id, "document_id": chunk.document_id, "page_number": chunk.page_start}])
        db.add(question); count += 1
    db.commit(); return {"quiz_id": quiz.id, "count": count}
