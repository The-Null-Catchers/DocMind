from __future__ import annotations

import re
from dataclasses import dataclass
from .parsing import ParsedPage


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    token_count: int
    metadata: dict


def estimate_tokens(text: str) -> int:
    # Conservative language-agnostic estimate: punctuation/words + Arabic words.
    return max(1, len(re.findall(r"[\w\u0600-\u06FF]+|[^\w\s]", text, flags=re.UNICODE)))


def _paragraphs(text: str) -> list[str]:
    blocks = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z\u0600-\u06FF])", text)]
    return [p for p in blocks if p]


def _is_heading(text: str) -> bool:
    if len(text) > 140 or len(text.split()) > 15:
        return False
    return bool(re.match(r"^(#{1,6}\s+|\d+(?:\.\d+)*[.)]?\s+|[A-Z][A-Z\s]{3,}$)", text)) or text.endswith(":")


def chunk_pages(pages: list[ParsedPage], target_tokens: int = 650, overlap_tokens: int = 100) -> list[ChunkDraft]:
    if target_tokens < 100 or overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("Invalid chunk configuration")
    chunks: list[ChunkDraft] = []
    current: list[str] = []
    current_tokens = 0
    current_section: str | None = None

    def flush(page_number: int, *, keep_overlap: bool = True) -> None:
        nonlocal current, current_tokens
        if not current:
            return
        text = "\n\n".join(current)
        chunks.append(ChunkDraft(
            text=text,
            chunk_index=len(chunks),
            page_start=page_number,
            page_end=page_number,
            section_title=current_section,
            token_count=estimate_tokens(text),
            metadata={"paragraph_count": len(current)},
        ))
        # Preserve a paragraph-aware overlap window.
        if not keep_overlap or not overlap_tokens:
            current = []
            current_tokens = 0
            return
        overlap: list[str] = []
        total = 0
        for item in reversed(current):
            cost = estimate_tokens(item)
            if overlap and total + cost > overlap_tokens:
                break
            overlap.append(item)
            total += cost
        current = list(reversed(overlap))
        current_tokens = total

    for page in pages:
        for paragraph in _paragraphs(page.text):
            if _is_heading(paragraph):
                if current and current_tokens >= max(100, target_tokens // 2):
                    flush(page.page_number)
                current_section = paragraph[:500]
            cost = estimate_tokens(paragraph)
            if current and current_tokens + cost > target_tokens:
                flush(page.page_number)
            if cost > target_tokens:
                words = paragraph.split()
                step = max(50, target_tokens - overlap_tokens)
                for start in range(0, len(words), step):
                    piece = " ".join(words[start:start + target_tokens])
                    if piece:
                        current.append(piece)
                        current_tokens += estimate_tokens(piece)
                        flush(page.page_number)
                continue
            current.append(paragraph)
            current_tokens += cost
        flush(page.page_number, keep_overlap=False)
    return chunks
