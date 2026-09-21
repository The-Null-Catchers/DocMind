"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Braces, FileDown, GitCompareArrows, Sparkles } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type DocumentRow = { id: string; title: string; status: string; page_count?: number | null };
type Citation = { ordinal?: number; chunk_id: string; document_id: string; page_number: number | null; source_excerpt?: string; excerpt?: string };
type RagResult = { content: string; citations: Citation[] };
type ExtractionResult = { data: Record<string, unknown>; sources: Citation[] };
type Mode = "summary" | "compare" | "extract";

const invoiceSchema = JSON.stringify({
  type: "object",
  properties: {
    invoice_number: { type: ["string", "null"] },
    vendor: { type: ["string", "null"] },
    date: { type: ["string", "null"] },
    subtotal: { type: ["number", "null"] },
    tax: { type: ["number", "null"] },
    total: { type: ["number", "null"] },
  },
}, null, 2);

export default function AnalyzePage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const [mode, setMode] = useState<Mode>("summary");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [summaryStyle, setSummaryStyle] = useState("detailed");
  const [focus, setFocus] = useState("");
  const [schemaText, setSchemaText] = useState(invoiceSchema);
  const [result, setResult] = useState<RagResult | ExtractionResult | null>(null);

  const documents = useQuery({
    queryKey: ["documents", workspaceId],
    queryFn: () => api<DocumentRow[]>(`/documents?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const readyDocuments = useMemo(
    () => documents.data?.filter((document) => document.status === "ready") ?? [],
    [documents.data],
  );

  const exportResult = useMutation({
    mutationFn: (kind: "summary_pdf" | "extraction_json" | "extraction_csv") => {
      if (!workspaceId || !result) throw new Error("No analysis result is available to export.");
      const title = mode === "summary" ? "DocMind summary" : "DocMind extraction";
      const payload =
        kind === "summary_pdf" && "content" in result
          ? { title, content: result.content }
          : "data" in result
            ? { title, data: result.data }
            : null;
      if (!payload) throw new Error("This result cannot be exported in the selected format.");
      return api("/exports", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: workspaceId,
          kind,
          source_id: null,
          payload,
        }),
      });
    },
    onSuccess: () => toast.success("Export queued. Open Exports to download it when ready."),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not queue export"),
  });

  const analyze = useMutation({
    mutationFn: async () => {
      if (!workspaceId || selectedIds.size === 0) throw new Error("Select at least one ready document.");
      const document_ids = Array.from(selectedIds);
      if (mode === "summary") {
        return api<RagResult>("/summaries/generate", {
          method: "POST",
          body: JSON.stringify({ workspace_id: workspaceId, document_ids, language: "auto", style: summaryStyle }),
        });
      }
      if (mode === "compare") {
        if (document_ids.length < 2) throw new Error("Select at least two documents to compare.");
        return api<RagResult>("/compare", {
          method: "POST",
          body: JSON.stringify({ workspace_id: workspaceId, document_ids, language: "auto", focus: focus.trim() || null }),
        });
      }
      let schema: Record<string, unknown>;
      try {
        schema = JSON.parse(schemaText) as Record<string, unknown>;
      } catch {
        throw new Error("The extraction schema is not valid JSON.");
      }
      return api<ExtractionResult>("/extract", {
        method: "POST",
        body: JSON.stringify({ workspace_id: workspaceId, document_ids, language: "auto", schema_definition: schema }),
      });
    },
    onSuccess: setResult,
    onError: (error) => toast.error(error instanceof Error ? error.message : "Analysis failed"),
  });

  function toggleDocument(id: string) {
    setResult(null);
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const citations = result && "citations" in result ? result.citations : result && "sources" in result ? result.sources : [];

  if (!workspaceId) return <div className="p-8 text-sm text-ink/50">Select a workspace to analyze documents.</div>;

  return (
    <div className="grid h-full min-h-0 lg:grid-cols-[320px_1fr]">
      <aside className="min-h-0 overflow-auto border-e bg-panel p-4">
        <h1 className="text-xl font-semibold">Analyze</h1>
        <p className="mt-1 text-xs leading-5 text-ink/45">Summarize, compare, or extract structured data from persisted documents.</p>
        <div className="mt-5 space-y-1">
          {readyDocuments.map((document) => (
            <label key={document.id} className="flex cursor-pointer items-center gap-3 rounded-xl p-2 hover:bg-muted">
              <input type="checkbox" checked={selectedIds.has(document.id)} onChange={() => toggleDocument(document.id)}/>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{document.title}</span>
                <span className="text-xs text-ink/40">{document.page_count ? `${document.page_count} pages` : "Ready"}</span>
              </span>
            </label>
          ))}
          {documents.isLoading && <p className="py-4 text-sm text-ink/45">Loading documents…</p>}
          {!documents.isLoading && readyDocuments.length === 0 && <p className="py-6 text-sm text-ink/45">No ready documents yet.</p>}
        </div>
      </aside>

      <main className="min-h-0 overflow-auto p-6 lg:p-8">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-wrap gap-2">
            <ModeButton active={mode === "summary"} onClick={() => { setMode("summary"); setResult(null); }} icon={Sparkles} label="Summary"/>
            <ModeButton active={mode === "compare"} onClick={() => { setMode("compare"); setResult(null); }} icon={GitCompareArrows} label="Compare"/>
            <ModeButton active={mode === "extract"} onClick={() => { setMode("extract"); setResult(null); }} icon={Braces} label="Extract"/>
          </div>

          <section className="surface mt-5 p-5">
            {mode === "summary" && <label className="block text-sm">Summary style
              <select value={summaryStyle} onChange={(event) => setSummaryStyle(event.target.value)} className="mt-2 block w-full max-w-sm rounded-xl border bg-panel px-3 py-2">
                {["short","detailed","executive","bullet","study"].map((style) => <option key={style} value={style}>{style}</option>)}
              </select>
            </label>}
            {mode === "compare" && <label className="block text-sm">Optional comparison focus
              <textarea value={focus} onChange={(event) => setFocus(event.target.value)} rows={3} className="mt-2 w-full rounded-xl border bg-transparent p-3 outline-none focus:ring-2 focus:ring-accent/30" placeholder="e.g. compare methodology, pricing, risks, or timeline"/>
            </label>}
            {mode === "extract" && <label className="block text-sm">JSON Schema
              <textarea value={schemaText} onChange={(event) => setSchemaText(event.target.value)} rows={15} spellCheck={false} className="mt-2 w-full rounded-xl border bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100 outline-none focus:ring-2 focus:ring-accent/30"/>
            </label>}
            <button onClick={() => analyze.mutate()} disabled={analyze.isPending || selectedIds.size === 0} className="mt-4 rounded-xl bg-ink px-5 py-2.5 text-sm font-medium text-panel disabled:opacity-40">
              {analyze.isPending ? "Running…" : mode === "summary" ? "Generate summary" : mode === "compare" ? "Compare documents" : "Extract data"}
            </button>
          </section>

          {result && <section className="surface mt-5 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold">Result</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-ink/40">{citations.length} verified sources</span>
                {mode === "summary" && "content" in result && (
                  <button onClick={() => exportResult.mutate("summary_pdf")} disabled={exportResult.isPending} className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-40"><FileDown size={13}/>PDF</button>
                )}
                {mode === "extract" && "data" in result && (
                  <>
                    <button onClick={() => exportResult.mutate("extraction_json")} disabled={exportResult.isPending} className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-40"><FileDown size={13}/>JSON</button>
                    <button onClick={() => exportResult.mutate("extraction_csv")} disabled={exportResult.isPending} className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-40"><FileDown size={13}/>CSV</button>
                  </>
                )}
              </div>
            </div>
            {"content" in result ? (
              <article className="mt-5 text-sm leading-7"><ReactMarkdown remarkPlugins={[remarkGfm]}>{result.content}</ReactMarkdown></article>
            ) : (
              <pre className="mt-5 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">{JSON.stringify(result.data, null, 2)}</pre>
            )}
            {citations.length > 0 && <div className="mt-6 grid gap-2 md:grid-cols-2">
              {citations.map((citation, index) => (
                <Link key={citation.chunk_id} href={`/app/documents/${citation.document_id}?page=${citation.page_number ?? 1}&chunk=${encodeURIComponent(citation.chunk_id)}`} className="rounded-xl border p-3 hover:bg-muted/40">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/40">Source {citation.ordinal ?? index + 1}{citation.page_number ? ` · Page ${citation.page_number}` : ""}</p>
                  <p className="mt-1 line-clamp-3 text-xs leading-5 text-ink/60">{citation.source_excerpt ?? citation.excerpt ?? ""}</p>
                </Link>
              ))}
            </div>}
          </section>}
        </div>
      </main>
    </div>
  );
}

function ModeButton({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Sparkles; label: string }) {
  return <button onClick={onClick} className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-sm ${active ? "bg-ink text-panel" : "bg-panel hover:bg-muted"}`}><Icon size={15}/>{label}</button>;
}
