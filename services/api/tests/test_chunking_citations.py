from app.services.chunking import chunk_pages
from app.services.citations import build_source_context, resolve_citations, strip_unknown_citations
from app.services.parsing import ParsedPage
from app.services.retrieval import RetrievalHit


def test_chunking_preserves_page_ranges_and_sections():
    pages = [
        ParsedPage(1, "INTRODUCTION:\n\nDocMind keeps source metadata. This is a grounded paragraph."),
        ParsedPage(2, "METHODS:\n\nThe system chunks by structure and page boundaries. Citations remain linked."),
    ]
    chunks = chunk_pages(pages, target_tokens=100, overlap_tokens=20)
    assert chunks
    assert all(c.page_start >= 1 and c.page_end <= 2 for c in chunks)
    assert any(c.section_title for c in chunks)


def test_citations_only_resolve_real_retrieval_hits():
    hit = RetrievalHit("chunk-1", "doc-1", "Paper.pdf", 7, "Results", "Retention improved by 12 percent.", 0.9, 0.8, 1.0)
    _context, mapping = build_source_context([hit])
    answer = "Retention improved [C1], while another claim [C999] is unsupported."
    cleaned = strip_unknown_citations(answer, mapping)
    assert "[C1]" in cleaned
    assert "C999" not in cleaned
    citations = resolve_citations(cleaned, mapping)
    assert len(citations) == 1
    assert citations[0].page_number == 7
    assert citations[0].chunk_id == "chunk-1"
