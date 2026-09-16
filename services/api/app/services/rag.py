from __future__ import annotations

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


class RAGService:
    def __init__(self, db: Session, llm: LLMProvider | None = None):
        self.db = db
        self.llm = llm or get_llm_provider()
        self.retrieval = RetrievalService(db)
        self.reranker: RerankerProvider = get_reranker_provider()

    async def answer(
        self,
        *,
        workspace_id: str,
        question: str,
        document_ids: list[str] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> RAGResult:
        hits = await self.retrieval.search(workspace_id=workspace_id, query=question, document_ids=document_ids, limit=16)
        if hits:
            rerank_scores = await self.reranker.rerank(question, [h.text for h in hits])
            hits = [pair[0] for pair in sorted(zip(hits, rerank_scores, strict=True), key=lambda p: p[1], reverse=True)][:8]
        source_context, mapping = build_source_context(hits)
        prompt = get_prompt("rag_answer")
        messages = list(history or [])[-10:]
        messages.append({"role": "system", "content": source_context if source_context else "NO SOURCES RETRIEVED"})
        messages.append({"role": "user", "content": question})
        parts: list[str] = []
        async for part in self.llm.stream(system=prompt.system, messages=messages):
            parts.append(part)
        answer = strip_unknown_citations("".join(parts).strip(), mapping)
        citations = resolve_citations(answer, mapping)
        if hits and not citations:
            # A provider that ignored citation instructions is treated as ungrounded, not silently trusted.
            answer += "\n\n_Source support was retrieved, but the model did not return valid citation markers._"
        return RAGResult(answer=answer, citations=citations, hits=hits)

    async def stream_answer(self, **kwargs) -> AsyncIterator[tuple[str, object]]:  # type: ignore[no-untyped-def]
        result = await self.answer(**kwargs)
        for token in result.answer.split(" "):
            yield "token", token + " "
        yield "citations", [c.__dict__ for c in result.citations]
