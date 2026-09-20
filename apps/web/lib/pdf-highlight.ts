export function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeRegExp(value: string): string {
  const specials = new Set(["\\\\", "^", "$", ".", "*", "+", "?", "(", ")", "[", "]", "{", "}", "|"]);
  return [...value].map((character) => specials.has(character) ? `\\\\${character}` : character).join("");
}

export function citationTerms(sourceExcerpt?: string | null): string[] {
  if (!sourceExcerpt) return [];
  const words = sourceExcerpt.match(/[\p{L}\p{N}][\p{L}\p{N}_-]{3,}/gu) ?? [];
  return Array.from(new Set(words.map((word) => word.toLocaleLowerCase())))
    .sort((a, b) => b.length - a.length)
    .slice(0, 40);
}

export function renderHighlightedPdfText(text: string, sourceExcerpt?: string | null): string {
  const terms = citationTerms(sourceExcerpt);
  if (!terms.length) return escapeHtml(text);

  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "giu");
  let cursor = 0;
  let result = "";
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    result += escapeHtml(text.slice(cursor, index));
    result += `<mark class="docmind-pdf-highlight">${escapeHtml(match[0])}</mark>`;
    cursor = index + match[0].length;
  }
  result += escapeHtml(text.slice(cursor));
  return result;
}
