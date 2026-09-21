"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CircleAlert, ChevronLeft, ChevronRight, Loader2, Maximize2, Minus, Plus } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";

import { renderHighlightedPdfText } from "@/lib/pdf-highlight";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfViewer({
  fileUrl,
  page,
  pageCount,
  zoom,
  highlightText,
  onPageChange,
  onZoomChange,
  onSelectionChange,
}: {
  fileUrl?: string;
  page: number;
  pageCount?: number | null;
  zoom: number;
  highlightText?: string | null;
  onPageChange: (page: number) => void;
  onZoomChange: (zoom: number) => void;
  onSelectionChange?: (text: string | null) => void;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewportWidth, setViewportWidth] = useState(0);
  const [pdfPageCount, setPdfPageCount] = useState<number | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const update = () => setViewportWidth(element.clientWidth);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setLoadError(false);
    setPdfPageCount(null);
    onSelectionChange?.(null);
  }, [fileUrl, page, onSelectionChange]);

  function reportSelection() {
    const container = viewportRef.current;
    const selection = window.getSelection();
    if (!container || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
      onSelectionChange?.(null);
      return;
    }
    const range = selection.getRangeAt(0);
    const common = range.commonAncestorContainer;
    const commonNode = common.nodeType === Node.TEXT_NODE ? common.parentNode : common;
    if (!commonNode || !container.contains(commonNode)) {
      onSelectionChange?.(null);
      return;
    }
    const text = selection.toString().replace(/\s+/g, " ").trim();
    onSelectionChange?.(text.length >= 2 ? text.slice(0, 12000) : null);
  }

  const maxPage = pdfPageCount ?? (pageCount && pageCount > 0 ? pageCount : undefined);
  const canNext = maxPage == null || page < maxPage;
  const baseWidth = Math.max(320, Math.min(Math.max(viewportWidth - 32, 320), 1100));
  const renderWidth = Math.round(baseWidth * (zoom / 100));
  const textRenderer = useMemo(
    () => ({ str }: { str: string }) => renderHighlightedPdfText(str, highlightText),
    [highlightText],
  );

  return (
    <div className="flex h-full min-h-0 flex-col bg-muted/35">
      <div className="flex h-12 shrink-0 items-center justify-between border-b bg-panel px-3">
        <div className="flex items-center gap-1">
          <button className="focus-ring rounded-lg p-2 hover:bg-muted disabled:opacity-30" onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page <= 1} aria-label="Previous page"><ChevronLeft size={15}/></button>
          <span className="min-w-24 text-center text-xs">Page {page}{maxPage ? ` / ${maxPage}` : ""}</span>
          <button className="focus-ring rounded-lg p-2 hover:bg-muted disabled:opacity-30" onClick={() => onPageChange(page + 1)} disabled={!canNext} aria-label="Next page"><ChevronRight size={15}/></button>
        </div>
        <div className="flex items-center gap-1">
          <button className="focus-ring rounded-lg p-2 hover:bg-muted" onClick={() => onZoomChange(Math.max(50, zoom - 10))} aria-label="Zoom out"><Minus size={15}/></button>
          <span className="w-12 text-center text-xs">{zoom}%</span>
          <button className="focus-ring rounded-lg p-2 hover:bg-muted" onClick={() => onZoomChange(Math.min(200, zoom + 10))} aria-label="Zoom in"><Plus size={15}/></button>
          <button className="focus-ring ms-1 rounded-lg p-2 hover:bg-muted" onClick={() => onZoomChange(100)} aria-label="Fit page width" title="Fit width"><Maximize2 size={15}/></button>
        </div>
      </div>

      <div
        ref={viewportRef}
        onMouseUp={reportSelection}
        onKeyUp={reportSelection}
        className="min-h-0 flex-1 overflow-auto p-4"
      >
        {!fileUrl ? (
          <div className="grid h-full min-h-72 place-items-center p-8 text-center text-sm text-ink/45">The original PDF preview is unavailable. Extracted page text can still be read and cited.</div>
        ) : loadError ? (
          <div className="mx-auto mt-12 flex max-w-md items-start gap-3 rounded-2xl border bg-panel p-5 text-sm">
            <CircleAlert className="mt-0.5 shrink-0 text-red-500" size={18}/>
            <div><p className="font-medium">PDF preview failed to load</p><p className="mt-1 text-xs leading-5 text-ink/50">The original file could not be rendered in the browser. You can still use extracted page text and citations.</p></div>
          </div>
        ) : (
          <Document
            file={fileUrl}
            loading={<div className="grid min-h-72 place-items-center"><Loader2 className="animate-spin text-ink/35"/></div>}
            onLoadSuccess={({ numPages }) => {
              setPdfPageCount(numPages);
              if (page > numPages) onPageChange(numPages);
            }}
            onLoadError={() => setLoadError(true)}
            className="mx-auto w-max"
          >
            <Page
              pageNumber={page}
              width={renderWidth}
              renderAnnotationLayer
              renderTextLayer
              customTextRenderer={textRenderer}
              loading={<div className="grid min-h-72 place-items-center"><Loader2 className="animate-spin text-ink/35"/></div>}
              className="overflow-hidden rounded-md bg-white shadow-soft"
            />
          </Document>
        )}
      </div>
    </div>
  );
}
