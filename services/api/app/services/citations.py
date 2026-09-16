from __future__ import annotations

import re
from dataclasses import dataclass
from .retrieval import RetrievalHit


@dataclass(frozen=True)
class Citation:
    ordinal: int
    label: str
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int | None
    source_excerpt: str
    deep_link: str


def build_source_context(hits: list[RetrievalHit]) -> tuple[str, dict[str, RetrievalHit]]:
    mapping: dict[str, RetrievalHit] = {}
    sections: list[str] = []
    for i, hit in enumerate(hits, start=1):
        label = f"C{i}"
        mapping[label] = hit
        page = str(hit.page_number) if hit.page_number is not None else "unknown"
        sections.append(
            f"[SOURCE {label}]\nDocument: {hit.document_title}\nDocument ID: {hit.document_id}\n"
            f"Chunk ID: {hit.chunk_id}\nPage: {page}\n{hit.text}"
        )
    return "\n\n".join(sections), mapping


def resolve_citations(answer: str, mapping: dict[str, RetrievalHit]) -> list[Citation]:
    used: list[str] = []
    for label in re.findall(r"\[(C\d+)\]", answer):
        if label in mapping and label not in used:
            used.append(label)
    citations: list[Citation] = []
    for ordinal, label in enumerate(used, start=1):
        hit = mapping[label]
        excerpt = re.sub(r"\s+", " ", hit.text).strip()[:500]
        page = hit.page_number
        anchor = f"?page={page}" if page is not None else ""
        citations.append(Citation(
            ordinal=ordinal,
            label=label,
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            document_name=hit.document_title,
            page_number=page,
            source_excerpt=excerpt,
            deep_link=f"/documents/{hit.document_id}{anchor}&chunk={hit.chunk_id}" if anchor else f"/documents/{hit.document_id}?chunk={hit.chunk_id}",
        ))
    return citations


def strip_unknown_citations(answer: str, mapping: dict[str, RetrievalHit]) -> str:
    def replace(match: re.Match[str]) -> str:
        label = match.group(1)
        return match.group(0) if label in mapping else ""
    return re.sub(r"\[(C\d+)\]", replace, answer)
