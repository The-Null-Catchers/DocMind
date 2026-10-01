from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import literal_column, or_, select, text
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
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if not denom:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / denom


def _keyword_score(query: str, value: str, exact_phrase: bool) -> float:
    q = re.sub(r"\s+", " ", query.casefold()).strip()
    haystack = re.sub(r"\s+", " ", value.casefold())
    if exact_phrase:
        return 1.0 if q in haystack else 0.0
    terms = set(re.findall(r"[\w\u0600-\u06FF]+", q, flags=re.UNICODE))
    if not terms:
        return 0.0
    text_terms = set(re.findall(r"[\w\u0600-\u06FF]+", haystack, flags=re.UNICODE))
    return len(terms & text_terms) / len(terms)


class RetrievalService:
    def __init__(self, db: Session, embedder: EmbeddingProvider | None = None):
        self.db = db
        self.embedder = embedder or get_embedding_provider()

    def _filters(
        self,
        *,
        workspace_id: str,
        document_ids: list[str] | None,
        folder_id: str | None,
        mime_types: list[str] | None,
        tag_ids: list[str] | None,
        created_after: datetime | None,
        created_before: datetime | None,
    ) -> list:
        filters = [
            DocumentChunk.workspace_id == workspace_id,
            Document.workspace_id == workspace_id,
            Document.deleted_at.is_(None),
            Document.status == "ready",
        ]
        if document_ids:
            filters.append(DocumentChunk.document_id.in_(document_ids))
        if folder_id:
            filters.append(Document.folder_id == folder_id)
        if mime_types:
            filters.append(Document.mime_type.in_(mime_types))
        if tag_ids:
            filters.append(
                Document.id.in_(
                    select(DocumentTag.document_id).where(DocumentTag.tag_id.in_(tag_ids))
                )
            )
        if created_after:
            filters.append(Document.created_at >= created_after)
        if created_before:
            filters.append(Document.created_at <= created_before)
        return filters

    async def _postgres_candidates(
        self,
        *,
        query: str,
        filters: list,
        mode: str,
        limit: int,
    ) -> tuple[list[tuple[DocumentChunk, Document, float]], list[float]]:
        query_vector = (await self.embedder.embed([query]))[0]
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in query_vector) + "]"
        distance = literal_column(
            "embeddings.vector_native <=> CAST(:query_vector AS vector)"
        )
        candidate_limit = max(200, limit * 40)
        statement = (
            select(DocumentChunk, Document, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .join(
                Embedding,
                (Embedding.chunk_id == DocumentChunk.id)
                & (Embedding.provider == self.embedder.name)
                & (Embedding.model == self.embedder.model),
            )
            .where(*filters, text("embeddings.vector_native IS NOT NULL"))
            .order_by(distance.asc())
            .limit(candidate_limit)
        )
        semantic_rows = self.db.execute(
            statement,
            {"query_vector": vector_literal},
        ).all()
        candidates: dict[str, tuple[DocumentChunk, Document, float]] = {
            chunk.id: (chunk, document, max(-1.0, 1.0 - float(distance_value)))
            for chunk, document, distance_value in semantic_rows
        }

        if mode == "hybrid":
            terms = list(
                dict.fromkeys(
                    re.findall(r"[\w\u0600-\u06FF]+", query.casefold(), flags=re.UNICODE)
                )
            )[:8]
            if terms:
                lexical_statement = (
                    select(DocumentChunk, Document, Embedding)
                    .join(Document, Document.id == DocumentChunk.document_id)
                    .outerjoin(
                        Embedding,
                        (Embedding.chunk_id == DocumentChunk.id)
                        & (Embedding.provider == self.embedder.name)
                        & (Embedding.model == self.embedder.model),
                    )
                    .where(
                        *filters,
                        or_(*[DocumentChunk.text.ilike(f"%{term}%") for term in terms]),
                    )
                    .limit(candidate_limit)
                )
                for chunk, document, embedding in self.db.execute(lexical_statement).all():
                    if chunk.id in candidates:
                        continue
                    semantic = (
                        _cosine(query_vector, embedding.vector_json)
                        if embedding and embedding.vector_json
                        else 0.0
                    )
                    candidates[chunk.id] = (chunk, document, semantic)

        return list(candidates.values()), query_vector

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
        filters = self._filters(
            workspace_id=workspace_id,
            document_ids=document_ids,
            folder_id=folder_id,
            mime_types=mime_types,
            tag_ids=tag_ids,
            created_after=created_after,
            created_before=created_before,
        )
        effective_exact = exact_phrase or mode == "exact"
        is_postgres = (
            self.db.bind is not None and self.db.bind.dialect.name == "postgresql"
        )

        ranked: list[RetrievalHit] = []
        if is_postgres and mode in {"semantic", "hybrid"} and not effective_exact:
            candidates, _query_vector = await self._postgres_candidates(
                query=query,
                filters=filters,
                mode=mode,
                limit=limit,
            )
            for chunk, document, semantic in candidates:
                keyword = _keyword_score(query, chunk.text, False)
                score = semantic if mode == "semantic" else (0.68 * semantic) + (0.32 * keyword)
                ranked.append(
                    RetrievalHit(
                        chunk_id=chunk.id,
                        document_id=document.id,
                        document_title=document.title,
                        page_number=chunk.page_start,
                        section_title=chunk.section_title,
                        text=chunk.text,
                        score=score,
                        semantic_score=semantic,
                        keyword_score=keyword,
                    )
                )
        else:
            statement = (
                select(DocumentChunk, Document, Embedding)
                .join(Document, Document.id == DocumentChunk.document_id)
                .outerjoin(
                    Embedding,
                    (Embedding.chunk_id == DocumentChunk.id)
                    & (Embedding.provider == self.embedder.name)
                    & (Embedding.model == self.embedder.model),
                )
                .where(*filters)
                .limit(2000)
            )
            candidates = self.db.execute(statement).all()
            query_vector: list[float] | None = None
            if mode in {"semantic", "hybrid"}:
                query_vector = (await self.embedder.embed([query]))[0]

            for chunk, document, embedding in candidates:
                semantic = (
                    _cosine(query_vector, embedding.vector_json)
                    if query_vector is not None and embedding
                    else 0.0
                )
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
                    score = (0.68 * semantic) + (0.32 * keyword)
                ranked.append(
                    RetrievalHit(
                        chunk_id=chunk.id,
                        document_id=document.id,
                        document_title=document.title,
                        page_number=chunk.page_start,
                        section_title=chunk.section_title,
                        text=chunk.text,
                        score=score,
                        semantic_score=semantic,
                        keyword_score=keyword,
                    )
                )

        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return ranked[:limit]
