"use client";

import { ChevronLeft, ChevronRight, Minus, Plus } from "lucide-react";

export function PdfViewer({
  fileUrl,
  page,
  pageCount,
  zoom,
  onPageChange,
  onZoomChange,
}: {
  fileUrl?: string;
  page: number;
  pageCount?: number | null;
  zoom: number;
  onPageChange: (page: number) => void;
  onZoomChange: (zoom: number) => void;
}) {
  const maxPage = pageCount && pageCount > 0 ? pageCount : undefined;
  const canNext = maxPage == null || page < maxPage;
  const target = fileUrl ? `${fileUrl}#page=${page}&zoom=${zoom}` : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col bg-muted/35">
      <div className="flex h-12 shrink-0 items-center justify-between border-b bg-panel px-3">
        <div className="flex items-center gap-1">
          <button className="rounded-lg p-2 hover:bg-muted disabled:opacity-30" onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page <= 1} aria-label="Previous page"><ChevronLeft size={15}/></button>
          <span className="min-w-24 text-center text-xs">Page {page}{maxPage ? ` / ${maxPage}` : ""}</span>
          <button className="rounded-lg p-2 hover:bg-muted disabled:opacity-30" onClick={() => onPageChange(page + 1)} disabled={!canNext} aria-label="Next page"><ChevronRight size={15}/></button>
        </div>
        <div className="flex items-center gap-1">
          <button className="rounded-lg p-2 hover:bg-muted" onClick={() => onZoomChange(Math.max(50, zoom - 10))} aria-label="Zoom out"><Minus size={15}/></button>
          <span className="w-12 text-center text-xs">{zoom}%</span>
          <button className="rounded-lg p-2 hover:bg-muted" onClick={() => onZoomChange(Math.min(200, zoom + 10))} aria-label="Zoom in"><Plus size={15}/></button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        {target ? (
          <iframe key={target} src={target} title="Document PDF" className="h-full w-full border-0 bg-white" />
        ) : (
          <div className="grid h-full place-items-center p-8 text-center text-sm text-ink/45">The original PDF preview is unavailable. Extracted page text can still be read and cited.</div>
        )}
      </div>
    </div>
  );
}
