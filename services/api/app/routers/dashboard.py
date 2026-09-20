from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import (
    AuditLog,
    Conversation,
    Document,
    DocumentPage,
    Flashcard,
    FlashcardDeck,
    Quiz,
    UsageRecord,
    User,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _document_out(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "status": document.status,
        "processing_progress": document.processing_progress,
        "page_count": document.page_count,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


@router.get("")
def dashboard(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_workspace_role(db, workspace_id, user.id, "viewer")

    document_scope = (
        Document.workspace_id == workspace_id,
        Document.deleted_at.is_(None),
    )
    documents = db.scalars(
        select(Document)
        .where(*document_scope)
        .order_by(Document.updated_at.desc())
        .limit(8)
    ).all()
    processing_documents = db.scalars(
        select(Document)
        .where(
            *document_scope,
            Document.status.notin_(("ready", "failed")),
        )
        .order_by(Document.updated_at.desc())
        .limit(8)
    ).all()

    document_totals = db.execute(
        select(
            func.count(Document.id),
            func.coalesce(func.sum(Document.file_size), 0),
            func.coalesce(func.sum(Document.page_count), 0),
        ).where(*document_scope)
    ).one()
    total_documents = int(document_totals[0] or 0)
    storage_bytes = int(document_totals[1] or 0)
    processed_pages = int(document_totals[2] or 0)

    status_rows = db.execute(
        select(Document.status, func.count(Document.id))
        .where(*document_scope)
        .group_by(Document.status)
    ).all()
    status_counts = {str(status): int(count) for status, count in status_rows}

    ocr_pages = int(
        db.scalar(
            select(func.count(DocumentPage.id))
            .join(Document, Document.id == DocumentPage.document_id)
            .where(
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                DocumentPage.ocr_used.is_(True),
            )
        )
        or 0
    )

    conversations = db.scalars(
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user.id,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(6)
    ).all()

    quizzes = db.scalars(
        select(Quiz)
        .where(
            Quiz.workspace_id == workspace_id,
            Quiz.user_id == user.id,
        )
        .order_by(Quiz.updated_at.desc())
        .limit(6)
    ).all()

    now = datetime.now(timezone.utc)
    due_flashcards = int(
        db.scalar(
            select(func.count(Flashcard.id))
            .join(FlashcardDeck, FlashcardDeck.id == Flashcard.deck_id)
            .where(
                FlashcardDeck.workspace_id == workspace_id,
                FlashcardDeck.user_id == user.id,
                (Flashcard.due_at.is_(None)) | (Flashcard.due_at <= now),
            )
        )
        or 0
    )

    usage_rows = db.execute(
        select(UsageRecord.metric, func.coalesce(func.sum(UsageRecord.quantity), 0))
        .where(UsageRecord.workspace_id == workspace_id)
        .group_by(UsageRecord.metric)
    ).all()
    usage = {str(metric): float(quantity or 0) for metric, quantity in usage_rows}

    activity = db.scalars(
        select(AuditLog)
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    ).all()

    return {
        "documents": {
            "total": total_documents,
            "ready": status_counts.get("ready", 0),
            "processing": sum(
                count
                for status, count in status_counts.items()
                if status not in {"ready", "failed"}
            ),
            "failed": status_counts.get("failed", 0),
            "storage_bytes": storage_bytes,
            "processed_pages": processed_pages,
            "ocr_pages": ocr_pages,
            "recent": [_document_out(document) for document in documents],
            "processing_items": [_document_out(document) for document in processing_documents],
        },
        "conversations": [
            {
                "id": conversation.id,
                "title": conversation.title,
                "pinned": conversation.pinned,
                "updated_at": conversation.updated_at,
            }
            for conversation in conversations
        ],
        "study": {
            "due_flashcards": due_flashcards,
            "recent_quizzes": [
                {
                    "id": quiz.id,
                    "title": quiz.title,
                    "difficulty": quiz.difficulty,
                    "language": quiz.language,
                    "updated_at": quiz.updated_at,
                }
                for quiz in quizzes
            ],
        },
        "usage": {
            "ai_messages": usage.get("ai_messages", 0),
            "metrics": usage,
        },
        "activity": [
            {
                "id": row.id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "actor_id": row.actor_id,
                "created_at": row.created_at,
            }
            for row in activity
        ],
    }
