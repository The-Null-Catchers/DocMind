from __future__ import annotations

import csv
import html
import io
import json
import re
from datetime import datetime, timezone

import fitz
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import (
    Conversation,
    ExportJob,
    Flashcard,
    FlashcardDeck,
    Message,
    MessageCitation,
    Note,
    Quiz,
    QuizQuestion,
)
from .notifications import notify_user
from .storage import get_storage


def _safe_filename(value: str, extension: str) -> str:
    stem = re.sub(r"[^\w\-. ()\u0600-\u06FF]", "_", value, flags=re.UNICODE).strip()
    stem = stem[:180] or "docmind-export"
    return f"{stem}.{extension}"


def _html_document(title: str, sections: list[tuple[str, str]]) -> str:
    pieces = [
        "<html><body>",
        f"<h1>{html.escape(title)}</h1>",
    ]
    for heading, text in sections:
        pieces.append(f"<h2>{html.escape(heading)}</h2>")
        pieces.append(
            "<p>"
            + html.escape(text).replace("\n", "<br>")
            + "</p>"
        )
    pieces.append("</body></html>")
    return "".join(pieces)


def _pdf_bytes(title: str, sections: list[tuple[str, str]]) -> bytes:
    stream = io.BytesIO()
    story = fitz.Story(
        html=_html_document(title, sections),
        user_css=(
            "body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; } "
            "h1 { font-size: 22pt; } h2 { font-size: 14pt; margin-top: 16pt; }"
        ),
    )
    writer = fitz.DocumentWriter(stream, "compress")
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (42, 42, -42, -42)
    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return stream.getvalue()


class ExportService:
    def __init__(self, db: Session):
        self.db = db

    def _note(self, job: ExportJob) -> tuple[bytes, str, str]:
        note = self.db.scalar(
            select(Note).where(
                Note.id == job.source_id,
                Note.workspace_id == job.workspace_id,
                Note.user_id == job.user_id,
            )
        )
        if not note:
            raise ValueError("Note not found")
        if job.kind == "note_markdown":
            return (
                note.content_markdown.encode("utf-8"),
                _safe_filename(note.title, "md"),
                "text/markdown; charset=utf-8",
            )
        return (
            _pdf_bytes(note.title, [("Note", note.content_markdown)]),
            _safe_filename(note.title, "pdf"),
            "application/pdf",
        )

    def _chat_sections(self, conversation: Conversation) -> list[tuple[str, str]]:
        rows = self.db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        ).all()
        sections: list[tuple[str, str]] = []
        for message in rows:
            if message.status not in {"complete", "cancelled"}:
                continue
            text = message.content
            citations = self.db.scalars(
                select(MessageCitation)
                .where(MessageCitation.message_id == message.id)
                .order_by(MessageCitation.ordinal.asc())
            ).all()
            if citations:
                sources = "\n".join(
                    f"[{citation.ordinal}] document={citation.document_id} "
                    f"page={citation.page_number or '-'} — {citation.source_excerpt}"
                    for citation in citations
                )
                text = f"{text}\n\nSources:\n{sources}"
            sections.append((message.role.capitalize(), text))
        return sections

    def _chat(self, job: ExportJob) -> tuple[bytes, str, str]:
        conversation = self.db.scalar(
            select(Conversation).where(
                Conversation.id == job.source_id,
                Conversation.workspace_id == job.workspace_id,
                Conversation.user_id == job.user_id,
            )
        )
        if not conversation:
            raise ValueError("Conversation not found")
        sections = self._chat_sections(conversation)
        if job.kind == "chat_markdown":
            content = [f"# {conversation.title}"]
            for heading, text in sections:
                content.extend(["", f"## {heading}", "", text])
            return (
                "\n".join(content).encode("utf-8"),
                _safe_filename(conversation.title, "md"),
                "text/markdown; charset=utf-8",
            )
        return (
            _pdf_bytes(conversation.title, sections),
            _safe_filename(conversation.title, "pdf"),
            "application/pdf",
        )

    def _flashcards(self, job: ExportJob) -> tuple[bytes, str, str]:
        deck = self.db.scalar(
            select(FlashcardDeck).where(
                FlashcardDeck.id == job.source_id,
                FlashcardDeck.workspace_id == job.workspace_id,
                FlashcardDeck.user_id == job.user_id,
            )
        )
        if not deck:
            raise ValueError("Flashcard deck not found")
        cards = self.db.scalars(
            select(Flashcard)
            .where(Flashcard.deck_id == deck.id)
            .order_by(Flashcard.created_at.asc())
        ).all()
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["front", "back", "difficulty", "tags", "sources"])
        for card in cards:
            writer.writerow([
                card.front,
                card.back,
                card.difficulty,
                ", ".join(card.tags or []),
                json.dumps(card.source_citations or [], ensure_ascii=False),
            ])
        return (
            stream.getvalue().encode("utf-8-sig"),
            _safe_filename(deck.name, "csv"),
            "text/csv; charset=utf-8",
        )

    def _quiz(self, job: ExportJob) -> tuple[bytes, str, str]:
        quiz = self.db.scalar(
            select(Quiz).where(
                Quiz.id == job.source_id,
                Quiz.workspace_id == job.workspace_id,
                Quiz.user_id == job.user_id,
            )
        )
        if not quiz:
            raise ValueError("Quiz not found")
        questions = self.db.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.created_at.asc())
        ).all()
        sections: list[tuple[str, str]] = []
        for index, question in enumerate(questions, 1):
            options = "\n".join(f"• {option}" for option in (question.options or []))
            text = question.question
            if options:
                text += f"\n\n{options}"
            text += f"\n\nAnswer: {question.answer}"
            if question.explanation:
                text += f"\nExplanation: {question.explanation}"
            sections.append((f"Question {index}", text))
        return (
            _pdf_bytes(quiz.title, sections),
            _safe_filename(quiz.title, "pdf"),
            "application/pdf",
        )

    def _payload_export(self, job: ExportJob) -> tuple[bytes, str, str]:
        payload = job.payload_json or {}
        title = str(payload.get("title") or "DocMind export")
        if job.kind == "summary_pdf":
            content = str(payload.get("content") or "")
            if not content:
                raise ValueError("Summary content is required")
            return (
                _pdf_bytes(title, [("Summary", content)]),
                _safe_filename(title, "pdf"),
                "application/pdf",
            )

        data = payload.get("data")
        if not isinstance(data, (dict, list)):
            raise ValueError("Extracted data payload is required")
        if job.kind == "extraction_json":
            return (
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
                _safe_filename(title, "json"),
                "application/json; charset=utf-8",
            )

        stream = io.StringIO()
        writer = csv.writer(stream)
        if isinstance(data, list):
            rows = [row for row in data if isinstance(row, dict)]
            headers = sorted({key for row in rows for key in row})
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row.get(header, "") for header in headers])
        elif isinstance(data, dict):
            writer.writerow(["field", "value"])
            for key, value in data.items():
                writer.writerow([
                    key,
                    json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else value,
                ])
        return (
            stream.getvalue().encode("utf-8-sig"),
            _safe_filename(title, "csv"),
            "text/csv; charset=utf-8",
        )

    def _render(self, job: ExportJob) -> tuple[bytes, str, str]:
        if job.kind in {"note_markdown", "note_pdf"}:
            return self._note(job)
        if job.kind in {"chat_markdown", "chat_pdf"}:
            return self._chat(job)
        if job.kind == "flashcards_csv":
            return self._flashcards(job)
        if job.kind == "quiz_pdf":
            return self._quiz(job)
        if job.kind in {"summary_pdf", "extraction_json", "extraction_csv"}:
            return self._payload_export(job)
        raise ValueError("Unsupported export kind")

    def process(self, job_id: str) -> None:
        job = self.db.get(ExportJob, job_id)
        if not job or job.status == "ready":
            return
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        self.db.commit()

        try:
            content, filename, mime_type = self._render(job)
            object_key = (
                f"workspaces/{job.workspace_id}/exports/{job.id}/{filename}"
            )
            get_storage().put_bytes(object_key, content, mime_type)
            job.object_key = object_key
            job.filename = filename
            job.mime_type = mime_type
            job.status = "ready"
            job.finished_at = datetime.now(timezone.utc)
            notify_user(
                self.db,
                user_id=job.user_id,
                kind="export_ready",
                title="Export ready",
                body=f"{filename} is ready to download.",
                data={"workspace_id": job.workspace_id, "export_id": job.id},
                preference_key="exports",
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            job = self.db.get(ExportJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.finished_at = datetime.now(timezone.utc)
                notify_user(
                    self.db,
                    user_id=job.user_id,
                    kind="export_failed",
                    title="Export failed",
                    body="DocMind could not create the requested export.",
                    data={"workspace_id": job.workspace_id, "export_id": job.id},
                    preference_key="exports",
                )
                self.db.commit()
            raise


def process_export_by_id(job_id: str) -> None:
    db = SessionLocal()
    try:
        ExportService(db).process(job_id)
    finally:
        db.close()
