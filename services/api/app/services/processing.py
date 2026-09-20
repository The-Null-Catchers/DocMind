from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from sqlalchemy import delete, select, text as sql_text
from sqlalchemy.orm import Session
from ..ai.providers import get_embedding_provider, get_ocr_provider
from ..config import get_settings
from ..db import SessionLocal
from ..models import Document, DocumentChunk, DocumentPage, DocumentProcessingJob, Embedding
from .chunking import chunk_pages
from .parsing import ParsedPage, parse_document
from .storage import get_storage
from .notifications import notify_user


class DocumentProcessingService:
    STAGES = ["validating", "parsing", "ocr", "chunking", "embedding", "indexing"]

    def __init__(self, db: Session):
        self.db = db

    def _set_status(self, document: Document, status: str, progress: int, error: str | None = None) -> None:
        document.status = status
        document.processing_progress = progress
        document.error_message = error
        self.db.commit()

    def _job(self, document_id: str, stage: str) -> DocumentProcessingJob:
        key = f"{document_id}:{stage}:v1"
        job = self.db.scalar(select(DocumentProcessingJob).where(
            DocumentProcessingJob.document_id == document_id,
            DocumentProcessingJob.job_key == key,
        ))
        if not job:
            job = DocumentProcessingJob(document_id=document_id, job_key=key, stage=stage, status="pending")
            self.db.add(job)
            self.db.flush()
        return job

    def _mark_job(self, document_id: str, stage: str, status: str, error: str | None = None) -> None:
        job = self._job(document_id, stage)
        now = datetime.now(timezone.utc)
        job.status = status
        if status == "processing":
            job.attempts += 1
            job.started_at = now
            job.error_message = None
        elif status in {"completed", "failed"}:
            job.finished_at = now
            job.error_message = error
        self.db.commit()

    async def process(self, document_id: str) -> None:
        document = self.db.get(Document, document_id)
        if not document:
            return
        if document.status == "ready":
            return
        stage = "validating"
        try:
            self._mark_job(document_id, stage, "processing")
            self._set_status(document, "processing", 5)
            data = get_storage().get_bytes(document.object_key)
            self._mark_job(document_id, stage, "completed")

            stage = "parsing"
            self._mark_job(document_id, stage, "processing")
            parsed = parse_document(data, document.mime_type)
            self._mark_job(document_id, stage, "completed")
            self._set_status(document, "processing", 25)

            stage = "ocr"
            self._mark_job(document_id, stage, "processing")
            ocr = get_ocr_provider()
            settings = get_settings()
            normalized_pages: list[ParsedPage] = []
            for page in parsed.pages:
                text = page.text.strip()
                ocr_used = False
                confidence = None
                if page.image_bytes is not None and len(text) < 20:
                    result = ocr.extract_image(page.image_bytes, settings.ocr_languages)
                    text = result.text
                    confidence = result.confidence
                    ocr_used = True
                normalized_pages.append(ParsedPage(page.page_number, text, {**page.metadata, "ocr_used": ocr_used, "ocr_confidence": confidence}))

            self._mark_job(document_id, stage, "completed")
            # Idempotent replacement of derived data. Cascades remove embeddings before rebuild.
            self.db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))
            self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            self.db.flush()
            for page in normalized_pages:
                self.db.add(DocumentPage(
                    document_id=document_id,
                    page_number=page.page_number,
                    text=page.text,
                    ocr_used=bool(page.metadata.get("ocr_used")),
                    ocr_confidence=page.metadata.get("ocr_confidence"),
                    metadata_json=page.metadata,
                ))
            document.page_count = len(normalized_pages)
            self.db.commit()
            self._set_status(document, "processing", 45)

            stage = "chunking"
            self._mark_job(document_id, stage, "processing")
            drafts = chunk_pages(normalized_pages, settings.default_chunk_tokens, settings.default_chunk_overlap)
            chunk_models: list[DocumentChunk] = []
            for draft in drafts:
                chunk = DocumentChunk(
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    chunk_index=draft.chunk_index,
                    text=draft.text,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    section_title=draft.section_title,
                    token_count=draft.token_count,
                    metadata_json=draft.metadata,
                )
                self.db.add(chunk)
                chunk_models.append(chunk)
            self.db.flush()
            self._mark_job(document_id, stage, "completed")
            self._set_status(document, "processing", 65)

            stage = "embedding"
            self._mark_job(document_id, stage, "processing")
            embedder = get_embedding_provider()
            vectors = await embedder.embed([chunk.text for chunk in chunk_models]) if chunk_models else []
            embeddings: list[tuple[Embedding, list[float]]] = []
            for chunk, vector in zip(chunk_models, vectors, strict=True):
                row = Embedding(
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    chunk_id=chunk.id,
                    provider=embedder.name,
                    model=embedder.model,
                    dimension=len(vector),
                    vector_json=vector,
                )
                self.db.add(row)
                embeddings.append((row, vector))
            self.db.flush()
            if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
                for row, vector in embeddings:
                    literal = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
                    self.db.execute(sql_text("UPDATE embeddings SET vector_native = CAST(:vector AS vector) WHERE id = :id"), {"vector": literal, "id": row.id})
            self.db.commit()
            self._mark_job(document_id, stage, "completed")
            stage = "indexing"
            self._mark_job(document_id, stage, "processing")
            self._mark_job(document_id, stage, "completed")
            self._set_status(document, "ready", 100)
            notify_user(
                self.db,
                user_id=document.uploaded_by_id,
                kind="document_processing_complete",
                title="Document ready",
                body=f"{document.title} is ready to search and chat with.",
                data={"workspace_id": document.workspace_id, "document_id": document.id},
                preference_key="document_processing",
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            try:
                self._mark_job(document_id, stage, "failed", str(exc)[:2000])
            except Exception:
                self.db.rollback()
            document = self.db.get(Document, document_id)
            if document:
                self._set_status(document, "failed", document.processing_progress or 0, str(exc)[:2000])
                notify_user(
                    self.db,
                    user_id=document.uploaded_by_id,
                    kind="document_processing_failed",
                    title="Document processing failed",
                    body=f"{document.title} could not be processed.",
                    data={
                        "workspace_id": document.workspace_id,
                        "document_id": document.id,
                    },
                    preference_key="document_processing",
                )
                self.db.commit()
            raise


def process_document_by_id(document_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(DocumentProcessingService(db).process(document_id))
    finally:
        db.close()
