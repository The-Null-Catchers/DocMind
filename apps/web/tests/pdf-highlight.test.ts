import { describe, expect, it } from "vitest";
import { citationTerms, renderHighlightedPdfText } from "../lib/pdf-highlight";

describe("PDF citation highlighting", () => {
  it("extracts useful English and Arabic citation terms", () => {
    expect(citationTerms("Grounded retrieval يربط الإجابة بالمصدر الصحيح")).toEqual(
      expect.arrayContaining(["grounded", "retrieval", "يربط", "الإجابة", "بالمصدر", "الصحيح"]),
    );
  });

  it("highlights only text that actually appears in the rendered PDF text item", () => {
    const rendered = renderHighlightedPdfText(
      "DocMind keeps grounded answers tied to source pages.",
      "Grounded answers are supported by source citations.",
    );
    expect(rendered).toContain('<mark class="docmind-pdf-highlight">grounded</mark>');
    expect(rendered).toContain('<mark class="docmind-pdf-highlight">answers</mark>');
    expect(rendered).toContain('<mark class="docmind-pdf-highlight">source</mark>');
    expect(rendered).not.toContain(">citations<");
  });

  it("escapes document text before returning markup", () => {
    const rendered = renderHighlightedPdfText("<script>alert('x')</script> grounded", "grounded source");
    expect(rendered).not.toContain("<script>");
    expect(rendered).toContain("&lt;script&gt;");
    expect(rendered).toContain('<mark class="docmind-pdf-highlight">grounded</mark>');
  });
});
