from __future__ import annotations

import re
from dataclasses import dataclass
from typing import AsyncIterator

from sqlalchemy.orm import Session

from ..ai.prompts import get_prompt
from ..ai.providers import LLMProvider, RerankerProvider, get_llm_provider, get_reranker_provider
from .citations import Citation, build_source_context, resolve_citations, strip_unknown_citations
from .retrieval import RetrievalHit, RetrievalService


@dataclass
class RAGResult:
    answer: str
    citations: list[Citation]
    hits: list[RetrievalHit]


@dataclass
class PreparedRAG:
    hits: list[RetrievalHit]
    messages: list[dict[str, str]]
    citation_mapping: dict


class _CitationDeltaSanitizer:
    """Keep model-authored citation markers out of unverified token events."""

    _pattern = re.compile(r"\[C\d+\]")
    _tail_size = 24

    def __init__(self) -> None:
        self._tail = ""

    def feed(self, delta: str) -> str:
        combined = self._tail + delta
        if len(combined) <= self._tail_size:
            self._tail = combined
            return ""
        emit, self._tail = combined[:-self._tail_size], combined[-self._tail_size:]
        return self._pattern.sub("", emit)

    def finish(self) -> str:
        value = self._pattern.sub("", self._tail)
        self._tail = ""
        return value


class RAGService:
    def __init__(self, db: Session, llm: LLMProvider | None = None):
        self.db = db
        self.llm = llm or get_llm_provider()
        self.retrieval = RetrievalService(db)
        self.reranker: RerankerProvider = get_reranker_provider()

    async def _prepare(
        self,
        *,
        workspace_id: str,
        question: str,
        document_ids: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> PreparedRAG:
        hits = await self.retrieval.search(
            workspace_id=workspace_id,
            query=question,
            document_ids=document_ids,
            limit=16,
        )
        if hits:
            rerank_scores = await self.reranker.rerank(question, [h.text for h in hits])
            hits = [
                pair[0]
                for pair in sorted(
                    zip(hits, rerank_scores, strict=True),
                    key=lambda pair: pair[1],
                    reverse=True,
                )
            ][:8]

        source_context, mapping = build_source_context(hits)
        messages = list(history or [])[-10:]
        messages.append(
            {
                "role": "system",
                "content": source_context if source_context else "NO SOURCES RETRIEVED",
            }
        )
        messages.append({"role": "user", "content": question})
        return PreparedRAG(hits=hits, messages=messages, citation_mapping=mapping)

    def _finalize(self, raw_answer: str, prepared: PreparedRAG) -> RAGResult:
        answer = strip_unknown_citations(raw_answer.strip(), prepared.citation_mapping)
        citations = resolve_citations(answer, prepared.citation_mapping)
        if prepared.hits and not citations:
            answer += (
                "\n\n_Source support was retrieved, but the model did not return "
                "valid citation markers._"
            )
        return RAGResult(answer=answer, citations=citations, hits=prepared.hits)

    async def answer(
        self,
        *,
        workspace_id: str,
        question: str,
        document_ids: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> RAGResult:
        prepared = await self._prepare(
            workspace_id=workspace_id,
            question=question,
            document_ids=document_ids,
            history=history,
        )
        prompt = get_prompt("rag_answer")
        parts: list[str] = []
        async for part in self.llm.stream(system=prompt.system, messages=prepared.messages):
            parts.append(part)
        return self._finalize("".join(parts), prepared)

    async def stream_answer(
        self,
        *,
        workspace_id: str,
        question: str,
        document_ids: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[tuple[str, object]]:
        prepared = await self._prepare(
            workspace_id=workspace_id,
            question=question,
            document_ids=document_ids,
            history=history,
        )
        yield "status", {"status": "generating"}

        prompt = get_prompt("rag_answer")
        raw_parts: list[str] = []
        sanitizer = _CitationDeltaSanitizer()
        async for part in self.llm.stream(system=prompt.system, messages=prepared.messages):
            raw_parts.append(part)
            safe_delta = sanitizer.feed(part)
            if safe_delta:
                yield "token", {"text": safe_delta}

        tail = sanitizer.finish()
        if tail:
            yield "token", {"text": tail}

        result = self._finalize("".join(raw_parts), prepared)
        yield "final", result
