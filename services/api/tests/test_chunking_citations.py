from app.services.chunking import chunk_pages
from app.services.citations import build_source_context, resolve_citations, strip_unknown_citations
from app.services.parsing import ParsedPage
from app.services.retrieval import RetrievalHit
from app.services.rag import _CitationDeltaSanitizer


def test_chunking_keeps_short_adjacent_pages_separate():
    pages = [
        ParsedPage(1, "INTRODUCTION:\n\nDocMind keeps source metadata. This is a grounded paragraph."),
        ParsedPage(2, "METHODS:\n\nThe system chunks by structure and page boundaries. Citations remain linked."),
    ]
    chunks = chunk_pages(pages, target_tokens=100, overlap_tokens=20)
    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 1), (2, 2)]
    assert [c.section_title for c in chunks] == ["INTRODUCTION:", "METHODS:"]
    assert "grounded paragraph" in chunks[0].text
    assert "grounded paragraph" not in chunks[1].text
    assert "Citations remain linked" in chunks[1].text


def test_chunking_preserves_field_lines_for_extraction():
    page = ParsedPage(1, "project: Atlas\napproved_budget_ils: 42000")
    [chunk] = chunk_pages([page])
    assert chunk.text == page.text


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


def test_stream_sanitizer_strips_split_model_citation_markers():
    sanitizer = _CitationDeltaSanitizer()
    output = [
        sanitizer.feed("Grounded answer ["),
        sanitizer.feed("C1] continues and [C"),
        sanitizer.feed("999] ends."),
        sanitizer.finish(),
    ]
    joined = "".join(output)
    assert "[C1]" not in joined
    assert "[C999]" not in joined
    assert "Grounded answer" in joined
    assert "continues" in joined
