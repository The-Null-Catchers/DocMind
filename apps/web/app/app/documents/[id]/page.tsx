"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { CircleAlert, Copy, Download, FileText, Loader2, MessageSquare, Search, Table2 } from "lucide-react";

import { ChatPanel } from "@/components/chat-panel";
import { PdfViewer } from "@/components/pdf-viewer";
import { SelectionActions } from "@/components/selection-actions";
import { api, apiBlob } from "@/lib/api";

type DocumentDetail = {
  id: string;
  workspace_id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  status: string;
  processing_progress: number;
  page_count: number | null;
  error_message?: string | null;
};

type PageData = {
  page_number: number;
  text: string;
  ocr_used: boolean;
  ocr_confidence: number | null;
  metadata: Record<string, unknown>;
};

type SearchHit = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  page_number: number | null;
  section_title: string | null;
  excerpt: string;
  score: number;
};

type DocumentTable = {
  page_number: number;
  table_index: number;
  row_count: number;
  column_count: number;
  truncated: boolean;
  rows: string[][];
};

type TableAnswer = {
  content: string;
  citation: {
    document_id: string;
    page_number: number;
    table_index: number;
    source_excerpt: string;
  };
};

export default function DocumentWorkspacePage() {
  const params = useParams<{ id: string | string[] }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const initialPage = Math.max(1, Number(searchParams.get("page") ?? 1) || 1);
  const [page, setPage] = useState(initialPage);
  const [zoom, setZoom] = useState(100);
  const [query, setQuery] = useState("");
  const [blobUrl, setBlobUrl] = useState<string>();
  const [highlightText, setHighlightText] = useState("");
  const [selectedText, setSelectedText] = useState("");
  const [tableAnswers, setTableAnswers] = useState<Record<string, string>>({});
  const [askingTable, setAskingTable] = useState<string | null>(null);
  const handleSelectionChange = useCallback((text: string | null) => {
    setSelectedText(text ?? "");
  }, []);

  const document = useQuery({
    queryKey: ["document", id],
    queryFn: () => api<DocumentDetail>(`/documents/${id}`),
    enabled: Boolean(id),
    refetchInterval: (queryState) => {
      const status = queryState.state.data?.status;
      return status && !["ready", "failed"].includes(status) ? 3000 : false;
    },
  });

  const currentPage = useQuery({
    queryKey: ["document-page", id, page],
    queryFn: () => api<PageData>(`/documents/${id}/pages/${page}`),
    enabled: Boolean(id) && document.data?.status === "ready",
    retry: false,
  });

  const tables = useQuery({
    queryKey: ["document-tables", id],
    queryFn: () => api<DocumentTable[]>(`/documents/${id}/tables`),
    enabled: Boolean(id) && document.data?.status === "ready",
    retry: false,
  });

  const search = useQuery({
    queryKey: ["document-search", id, query],
    queryFn: () => api<SearchHit[]>("/search", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: document.data!.workspace_id,
        query: query.trim(),
        document_ids: [id],
        exact_phrase: false,
        limit: 20,
      }),
    }),
    enabled: Boolean(document.data?.workspace_id && query.trim().length >= 2),
  });

  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    async function loadPdf() {
      if (document.data?.status !== "ready" || document.data.mime_type !== "application/pdf") {
        setBlobUrl(undefined);
        return;
      }
      try {
        const blob = await apiBlob(`/documents/${id}/file`);
        objectUrl = URL.createObjectURL(blob);
        if (active) setBlobUrl(objectUrl);
      } catch {
        if (active) setBlobUrl(undefined);
      }
    }
    void loadPdf();
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [document.data?.mime_type, document.data?.status, id]);

  function tableKey(table: DocumentTable) {
    return `${table.page_number}:${table.table_index}`;
  }

  function csvCell(value: string) {
    const safe = /^[=+@-]/.test(value) ? `'${value}` : value;
    return `"${safe.replaceAll('"', '""')}"`;
  }

  function tableCsv(table: DocumentTable) {
    return table.rows.map((row) => row.map((cell) => csvCell(String(cell ?? ""))).join(",")).join("\r\n");
  }

  async function copyTable(table: DocumentTable) {
    await navigator.clipboard.writeText(
      table.rows.map((row) => row.map((cell) => String(cell ?? "")).join("\t")).join("\n"),
    );
  }

  function downloadTable(table: DocumentTable) {
    const blob = new Blob([tableCsv(table)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `table-page-${table.page_number}-${table.table_index + 1}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function askAboutTable(table: DocumentTable) {
    const question = window.prompt("Ask a question about this table");
    if (!question?.trim()) return;
    const key = tableKey(table);
    setAskingTable(key);
    try {
      const answer = await api<TableAnswer>("/ai/table", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: document.data!.workspace_id,
          document_id: id,
          page_number: table.page_number,
          table_index: table.table_index,
          question: question.trim(),
        }),
      });
      setTableAnswers((current) => ({ ...current, [key]: answer.content }));
    } catch (error) {
      setTableAnswers((current) => ({
        ...current,
        [key]: error instanceof Error ? error.message : "Could not answer this table question.",
      }));
    } finally {
      setAskingTable(null);
    }
  }

  function goToPage(nextPage: number, chunkId?: string, excerpt?: string) {
    const maxPage = document.data?.page_count ?? nextPage;
    const bounded = Math.max(1, Math.min(nextPage, maxPage || nextPage));
    setPage(bounded);
    setHighlightText(excerpt ?? "");
    setSelectedText("");
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(bounded));
    if (chunkId) params.set("chunk", chunkId); else params.delete("chunk");
    router.replace(`?${params.toString()}`, { scroll: false });
  }

  const pageNumbers = useMemo(() => {
    const count = document.data?.page_count ?? 0;
    if (count <= 0) return [];
    const start = Math.max(1, page - 8);
    const end = Math.min(count, start + 16);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }, [document.data?.page_count, page]);

  if (document.isLoading) return <div className="grid h-full place-items-center"><Loader2 className="animate-spin text-ink/35"/></div>;
  if (document.isError || !document.data) return <div className="grid h-full place-items-center p-8"><div className="surface flex max-w-md items-start gap-3 p-5"><CircleAlert size={20} className="mt-0.5 text-red-500"/><div><h1 className="font-medium">Document unavailable</h1><p className="mt-1 text-sm text-ink/50">It may have been removed or you may no longer have access.</p></div></div></div>;

  const doc = document.data;
  if (doc.status !== "ready") {
    return <div className="grid h-full place-items-center p-8"><div className="surface max-w-lg p-7 text-center"><FileText className="mx-auto text-ink/30" size={32}/><h1 className="mt-4 text-lg font-semibold">{doc.title}</h1>{doc.status === "failed" ? <><p className="mt-2 text-sm text-red-600">Processing failed.</p><p className="mt-2 text-xs text-ink/45">{doc.error_message || "No additional error details are available."}</p></> : <><p className="mt-2 text-sm text-ink/50">Processing document… {doc.processing_progress ?? 0}%</p><div className="mx-auto mt-4 h-1.5 max-w-sm overflow-hidden rounded-full bg-muted"><div className="h-full bg-accent transition-all" style={{ width: `${doc.processing_progress ?? 0}%` }}/></div></>}</div></div>;
  }

  const isPdf = doc.mime_type === "application/pdf";
  return <div className="h-full">
    <PanelGroup direction="horizontal">
      <Panel defaultSize={18} minSize={14} maxSize={28}>
        <aside className="flex h-full min-h-0 flex-col border-e bg-panel">
          <div className="border-b p-3">
            <h1 className="truncate text-sm font-semibold" title={doc.title}>{doc.title}</h1>
            <p className="mt-0.5 text-[10px] text-ink/40">{doc.page_count ? `${doc.page_count} pages` : "Extracted document"}</p>
            <div className="relative mt-3"><Search className="absolute start-2.5 top-2.5 text-ink/35" size={14}/><input value={query} onChange={(event)=>setQuery(event.target.value)} className="w-full rounded-xl border bg-muted/30 py-2 pe-2 ps-8 text-xs outline-none focus:ring-2 focus:ring-accent/30" placeholder="Search in document"/></div>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-2">
            {query.trim().length >= 2 ? <>
              <p className="px-2 py-2 text-[10px] font-semibold uppercase tracking-widest text-ink/40">Search results</p>
              {search.isFetching && <p className="px-2 py-3 text-xs text-ink/40">Searching…</p>}
              {!search.isFetching && search.data?.length === 0 && <p className="px-2 py-3 text-xs text-ink/40">No matching passages.</p>}
              {search.data?.map((hit)=><button key={hit.chunk_id} onClick={()=>hit.page_number && goToPage(hit.page_number, hit.chunk_id, hit.excerpt)} className="mb-1 w-full rounded-lg px-2 py-2 text-left hover:bg-muted"><div className="flex items-center justify-between gap-2"><span className="truncate text-[11px] font-medium">{hit.section_title || "Passage"}</span><span className="shrink-0 text-[10px] text-ink/35">{hit.page_number ? `p. ${hit.page_number}` : ""}</span></div><p className="mt-1 line-clamp-3 text-[11px] leading-4 text-ink/50">{hit.excerpt}</p></button>)}
            </> : <>
              <p className="px-2 py-2 text-[10px] font-semibold uppercase tracking-widest text-ink/40">Pages</p>
              {pageNumbers.length ? <div className="grid grid-cols-4 gap-1 px-1">{pageNumbers.map((number)=><button key={number} onClick={()=>goToPage(number)} className={`rounded-lg px-2 py-2 text-xs ${number === page ? "bg-ink text-panel" : "hover:bg-muted"}`}>{number}</button>)}</div> : <p className="px-2 py-3 text-xs text-ink/40">Page count unavailable.</p>}
            </>}
          </div>
          {tables.data && tables.data.length > 0 && (
            <div className="max-h-[46%] overflow-auto border-t p-2">
              <p className="flex items-center gap-1.5 px-2 py-2 text-[10px] font-semibold uppercase tracking-widest text-ink/40">
                <Table2 size={12}/>Tables
              </p>
              <div className="space-y-2">
                {tables.data.map((table) => {
                  const key = tableKey(table);
                  return (
                    <div key={key} className="rounded-xl border bg-panel p-2">
                      <button onClick={() => goToPage(table.page_number)} className="flex w-full items-center justify-between gap-2 text-left">
                        <span className="text-[11px] font-semibold">Page {table.page_number} · Table {table.table_index + 1}</span>
                        <span className="text-[10px] text-ink/40">{table.row_count}×{table.column_count}</span>
                      </button>
                      <div className="mt-2 max-h-28 overflow-auto rounded-lg border">
                        <table className="min-w-full border-collapse text-[10px]">
                          <tbody>
                            {table.rows.slice(0, 6).map((row, rowIndex) => (
                              <tr key={rowIndex} className={rowIndex === 0 ? "bg-muted/60 font-medium" : ""}>
                                {row.map((cell, cellIndex) => (
                                  <td key={cellIndex} className="max-w-32 truncate border-b border-e px-2 py-1.5" title={String(cell ?? "")}>{String(cell ?? "")}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {table.truncated && <p className="mt-1 text-[9px] text-amber-600">Large table preview is truncated.</p>}
                      <div className="mt-2 flex flex-wrap gap-1">
                        <button onClick={() => void copyTable(table)} className="rounded-md border p-1.5 hover:bg-muted" title="Copy table"><Copy size={12}/></button>
                        <button onClick={() => downloadTable(table)} className="rounded-md border p-1.5 hover:bg-muted" title="Download CSV"><Download size={12}/></button>
                        <button onClick={() => void askAboutTable(table)} disabled={askingTable === key} className="flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] hover:bg-muted disabled:opacity-50" title="Ask AI about table">
                          <MessageSquare size={11}/>{askingTable === key ? "Asking…" : "Ask AI"}
                        </button>
                      </div>
                      {tableAnswers[key] && <p className="mt-2 whitespace-pre-wrap rounded-lg bg-muted/50 p-2 text-[10px] leading-4 text-ink/70">{tableAnswers[key]}</p>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </aside>
      </Panel>
      <PanelResizeHandle className="w-1 bg-transparent hover:bg-accent/30"/>
      <Panel defaultSize={52} minSize={34}>
        <div className="relative h-full min-h-0">
          {isPdf ? (
            <PdfViewer
              fileUrl={blobUrl}
              page={page}
              pageCount={doc.page_count}
              zoom={zoom}
              highlightText={highlightText}
              onPageChange={(nextPage)=>goToPage(nextPage)}
              onZoomChange={setZoom}
              onSelectionChange={handleSelectionChange}
            />
          ) : (
            <div className="flex h-full min-h-0 flex-col bg-muted/30">
              <div className="flex h-12 items-center border-b bg-panel px-4 text-xs text-ink/45">
                Page {page}{doc.page_count ? ` / ${doc.page_count}` : ""}{currentPage.data?.ocr_used ? " · OCR" : ""}
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-6">
                <article
                  tabIndex={0}
                  onMouseUp={() => {
                    const text = window.getSelection()?.toString().replace(/\s+/g, " ").trim() ?? "";
                    setSelectedText(text.length >= 2 ? text.slice(0, 12000) : "");
                  }}
                  onKeyUp={() => {
                    const text = window.getSelection()?.toString().replace(/\s+/g, " ").trim() ?? "";
                    setSelectedText(text.length >= 2 ? text.slice(0, 12000) : "");
                  }}
                  className="mx-auto max-w-4xl whitespace-pre-wrap rounded-2xl border bg-panel p-7 text-sm leading-7 shadow-sm outline-none focus:ring-2 focus:ring-accent/20"
                >
                  {currentPage.isLoading ? "Loading extracted text…" : currentPage.data?.text || "No extracted text is available for this page."}
                </article>
              </div>
            </div>
          )}
          {selectedText && (
            <SelectionActions
              workspaceId={doc.workspace_id}
              documentId={doc.id}
              page={page}
              selectedText={selectedText}
              onClear={() => {
                window.getSelection()?.removeAllRanges();
                setSelectedText("");
              }}
            />
          )}
        </div>
      </Panel>
      <PanelResizeHandle className="w-1 bg-transparent hover:bg-accent/30"/>
      <Panel defaultSize={30} minSize={24} maxSize={44}>
        <ChatPanel workspaceId={doc.workspace_id} documentId={doc.id} documentTitle={doc.title} onCitation={(citation)=>{if(citation.page_number) goToPage(citation.page_number, citation.chunk_id, citation.source_excerpt);}}/>
      </Panel>
    </PanelGroup>
  </div>;
}
