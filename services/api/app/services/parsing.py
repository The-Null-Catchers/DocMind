from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedPage:
    page_number: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    image_bytes: bytes | None = None


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    metadata: dict[str, Any] = field(default_factory=dict)


def _parse_pdf(data: bytes) -> ParsedDocument:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required to parse PDFs") from exc
    reader = PdfReader(io.BytesIO(data))
    rendered: dict[int, bytes] = {}
    pages: list[ParsedPage] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        image_bytes = None
        if len(text.strip()) < 20:
            # Scanned/mostly-image PDF fallback: rasterize just this page for OCR.
            try:
                import fitz
                pdf = fitz.open(stream=data, filetype="pdf")
                pix = pdf.load_page(i - 1).get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image_bytes = pix.tobytes("png")
                pdf.close()
            except Exception:
                image_bytes = None
        pages.append(ParsedPage(page_number=i, text=text, metadata={"kind": "pdf_page"}, image_bytes=image_bytes))
    return ParsedDocument(pages=pages, metadata={"title": reader.metadata.title if reader.metadata else None})


def _parse_docx(data: bytes) -> ParsedDocument:
    from docx import Document as DocxDocument
    doc = DocxDocument(io.BytesIO(data))
    blocks: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            blocks.append(text)
    for table in doc.tables:
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        if rows:
            blocks.append("\n".join(rows))
    return ParsedDocument([ParsedPage(1, "\n\n".join(blocks), {"kind": "docx"})])


def _parse_pptx(data: bytes) -> ParsedDocument:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(data))
    pages: list[ParsedPage] = []
    for i, slide in enumerate(prs.slides, start=1):
        texts: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and str(shape.text).strip():
                texts.append(str(shape.text).strip())
        pages.append(ParsedPage(i, "\n".join(texts), {"kind": "slide", "slide_number": i}))
    return ParsedDocument(pages)


def _parse_csv(data: bytes) -> ParsedDocument:
    decoded = data.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(decoded)))
    rendered = "\n".join(" | ".join(cell for cell in row) for row in rows)
    return ParsedDocument([ParsedPage(1, rendered, {"kind": "csv", "row_count": len(rows)})])


def parse_document(data: bytes, mime_type: str) -> ParsedDocument:
    if mime_type == "application/pdf":
        return _parse_pdf(data)
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _parse_docx(data)
    if mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        return _parse_pptx(data)
    if mime_type == "text/csv":
        return _parse_csv(data)
    if mime_type.startswith("text/"):
        return ParsedDocument([ParsedPage(1, data.decode("utf-8-sig", errors="replace"), {"kind": "text"})])
    if mime_type.startswith("image/"):
        return ParsedDocument([ParsedPage(1, "", {"kind": "image"}, image_bytes=data)])
    raise ValueError(f"Unsupported parser MIME type: {mime_type}")
