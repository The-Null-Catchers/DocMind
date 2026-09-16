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
    current: list[tuple[str, int]] = []
    current_tokens = 0
    current_section: str | None = None

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        text = "\n\n".join(part for part, _page in current).strip()
        pages_seen = [page for _part, page in current]
        chunks.append(ChunkDraft(
            text=text,
            chunk_index=len(chunks),
            page_start=min(pages_seen),
            page_end=max(pages_seen),
            section_title=current_section,
            token_count=estimate_tokens(text),
            metadata={"paragraph_count": len(current)},
        ))
        # Preserve a paragraph-aware overlap window.
        overlap: list[tuple[str, int]] = []
        total = 0
        for item in reversed(current):
            cost = estimate_tokens(item[0])
            if overlap and total + cost > overlap_tokens:
                break
            overlap.append(item)
            total += cost
        current = list(reversed(overlap)) if overlap_tokens else []
        current_tokens = sum(estimate_tokens(part) for part, _ in current)

    for page in pages:
        for paragraph in _paragraphs(page.text):
            if _is_heading(paragraph):
                if current and current_tokens >= max(100, target_tokens // 2):
                    flush()
                current_section = paragraph[:500]
            cost = estimate_tokens(paragraph)
            if current and current_tokens + cost > target_tokens:
                flush()
            if cost > target_tokens:
                words = paragraph.split()
                step = max(50, target_tokens - overlap_tokens)
                for start in range(0, len(words), step):
                    piece = " ".join(words[start:start + target_tokens])
                    if piece:
                        current.append((piece, page.page_number))
                        current_tokens += estimate_tokens(piece)
                        flush()
                continue
            current.append((paragraph, page.page_number))
            current_tokens += cost
    flush()
    return chunks
