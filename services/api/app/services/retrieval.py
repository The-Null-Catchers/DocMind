from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..ai.providers import EmbeddingProvider, get_embedding_provider
from ..models import Document, DocumentChunk, DocumentTag, Embedding


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    document_title: str
    page_number: int | None
    section_title: str | None
    text: str
    score: float
    semantic_score: float
    keyword_score: float


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    denom = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(y*y for y in b))
    if not denom:
        return 0.0
    return sum(x*y for x, y in zip(a, b, strict=True)) / denom


def _keyword_score(query: str, text: str, exact_phrase: bool) -> float:
    q = re.sub(r"\s+", " ", query.casefold()).strip()
    t = re.sub(r"\s+", " ", text.casefold())
    if exact_phrase:
        return 1.0 if q in t else 0.0
    terms = set(re.findall(r"[\w\u0600-\u06FF]+", q, flags=re.UNICODE))
    if not terms:
        return 0.0
    text_terms = set(re.findall(r"[\w\u0600-\u06FF]+", t, flags=re.UNICODE))
    return len(terms & text_terms) / len(terms)


class RetrievalService:
    def __init__(self, db: Session, embedder: EmbeddingProvider | None = None):
        self.db = db
        self.embedder = embedder or get_embedding_provider()

    async def search(
        self,
        *,
        workspace_id: str,
        query: str,
        document_ids: list[str] | None = None,
        folder_id: str | None = None,
        exact_phrase: bool = False,
        mode: str = "hybrid",
        mime_types: list[str] | None = None,
        tag_ids: list[str] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 12,
    ) -> list[RetrievalHit]:
        # Workspace predicate is mandatory at the lowest retrieval boundary.
        statement = (
            select(DocumentChunk, Document, Embedding)
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(
                Embedding,
                (Embedding.chunk_id == DocumentChunk.id)
                & (Embedding.provider == self.embedder.name)
                & (Embedding.model == self.embedder.model),
            )
            .where(
                DocumentChunk.workspace_id == workspace_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                Document.status == "ready",
            )
        )
        if document_ids:
            statement = statement.where(DocumentChunk.document_id.in_(document_ids))
        if folder_id:
            statement = statement.where(Document.folder_id == folder_id)
        if mime_types:
            statement = statement.where(Document.mime_type.in_(mime_types))
        if tag_ids:
            statement = statement.where(
                Document.id.in_(
                    select(DocumentTag.document_id).where(DocumentTag.tag_id.in_(tag_ids))
                )
            )
        if created_after:
            statement = statement.where(Document.created_at >= created_after)
        if created_before:
            statement = statement.where(Document.created_at <= created_before)
        candidates = self.db.execute(statement.limit(2000)).all()
        query_vector = (await self.embedder.embed([query]))[0]
        ranked: list[RetrievalHit] = []
        for chunk, document, embedding in candidates:
            semantic = _cosine(query_vector, embedding.vector_json) if embedding else 0.0
            effective_exact = exact_phrase or mode == "exact"
            keyword = _keyword_score(query, chunk.text, effective_exact)
            if effective_exact and keyword == 0:
                continue
            if mode == "keyword":
                score = keyword
            elif mode == "semantic":
                score = semantic
            elif mode == "exact":
                score = keyword
            else:
                # Weighted hybrid fusion; keyword receives a boost for exact/rare terms.
                score = (0.68 * semantic) + (0.32 * keyword)
            ranked.append(RetrievalHit(
                chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                page_number=chunk.page_start,
                section_title=chunk.section_title,
                text=chunk.text,
                score=score,
                semantic_score=semantic,
                keyword_score=keyword,
            ))
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return ranked[:limit]
