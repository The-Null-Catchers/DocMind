"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileDown, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, apiBlob } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type SourceKind = "note" | "chat" | "flashcards" | "quiz";

type SourceRow = {
  id: string;
  title?: string;
  name?: string;
};
type ExportJob = {
  id: string;
  kind: string;
  source_id: string | null;
  status: "pending" | "processing" | "ready" | "failed";
  filename: string | null;
  mime_type: string | null;
  error_message: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

const formats: Record<SourceKind, Array<{ label: string; kind: string }>> = {
  note: [
    { label: "Markdown", kind: "note_markdown" },
    { label: "PDF", kind: "note_pdf" },
  ],
  chat: [
    { label: "Markdown", kind: "chat_markdown" },
    { label: "PDF", kind: "chat_pdf" },
  ],
  flashcards: [{ label: "CSV", kind: "flashcards_csv" }],
  quiz: [{ label: "PDF", kind: "quiz_pdf" }],
};

export default function ExportsPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const queryClient = useQueryClient();
  const [sourceKind, setSourceKind] = useState<SourceKind>("note");
  const [sourceId, setSourceId] = useState("");
  const [exportKind, setExportKind] = useState(formats.note[0].kind);

  const notes = useQuery({
    queryKey: ["notes", workspaceId],
    queryFn: () => api<Array<{ id: string; title: string }>>(`/notes?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });
  const conversations = useQuery({
    queryKey: ["conversations", workspaceId],
    queryFn: () => api<Array<{ id: string; title: string }>>(`/conversations?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });
  const decks = useQuery({
    queryKey: ["flashcard-decks", workspaceId],
    queryFn: () => api<Array<{ id: string; name: string }>>(`/flashcards/decks?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });
  const quizzes = useQuery({
    queryKey: ["quizzes", workspaceId],
    queryFn: () => api<Array<{ id: string; title: string }>>(`/quizzes?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const jobs = useQuery({
    queryKey: ["exports", workspaceId],
    queryFn: () => api<ExportJob[]>(`/exports?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
    refetchInterval: (query) =>
      query.state.data?.some((job) => job.status === "pending" || job.status === "processing")
        ? 2500
        : false,
  });

  const sources = useMemo<SourceRow[]>(() => {
    if (sourceKind === "note") return notes.data ?? [];
    if (sourceKind === "chat") return conversations.data ?? [];
    if (sourceKind === "flashcards") return decks.data ?? [];
    return quizzes.data ?? [];
  }, [sourceKind, notes.data, conversations.data, decks.data, quizzes.data]);

  function changeSourceKind(next: SourceKind) {
    setSourceKind(next);
    setSourceId("");
    setExportKind(formats[next][0].kind);
  }

  const createExport = useMutation({
    mutationFn: () =>
      api<ExportJob>("/exports", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: workspaceId,
          kind: exportKind,
          source_id: sourceId,
          payload: {},
        }),
      }),
    onSuccess: async () => {
      toast.success("Export queued");
      await queryClient.invalidateQueries({ queryKey: ["exports", workspaceId] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not create export"),
  });

  const retryExport = useMutation({
    mutationFn: (id: string) => api<ExportJob>(`/exports/${id}/retry`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["exports", workspaceId] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not retry export"),
  });

  const deleteExport = useMutation({
    mutationFn: (id: string) => api<void>(`/exports/${id}`, { method: "DELETE" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["exports", workspaceId] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not delete export"),
  });

  async function downloadExport(job: ExportJob) {
    try {
      const result = await api<{ url: string }>(`/exports/${job.id}/download-url`);
      if (/^https?:\/\//i.test(result.url)) {
        window.open(result.url, "_blank", "noopener,noreferrer");
        return;
      }
      const blob = await apiBlob(`/exports/${job.id}/file`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = job.filename || "docmind-export";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not download export");
    }
  }

  if (!workspaceId) {
    return <div className="p-8 text-sm text-ink/50">Select a workspace to manage exports.</div>;
  }

  return (
    <div className="mx-auto max-w-6xl p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-semibold">Exports</h1>
        <p className="mt-1 text-sm text-ink/50">Create authorized downloads from your notes, chats, study content, and analysis results.</p>
      </div>

      <section className="surface mt-6 p-5">
        <h2 className="font-medium">Create export</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-[180px_1fr_160px_auto]">
          <label className="text-xs font-medium">Source type
            <select value={sourceKind} onChange={(event) => changeSourceKind(event.target.value as SourceKind)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2 text-sm">
              <option value="note">Note</option>
              <option value="chat">Chat</option>
              <option value="flashcards">Flashcards</option>
              <option value="quiz">Quiz</option>
            </select>
          </label>

          <label className="text-xs font-medium">Source
            <select value={sourceId} onChange={(event) => setSourceId(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2 text-sm">
              <option value="">Select source…</option>
              {sources.map((source) => <option key={source.id} value={source.id}>{source.title ?? source.name ?? source.id}</option>)}
            </select>
          </label>

          <label className="text-xs font-medium">Format
            <select value={exportKind} onChange={(event) => setExportKind(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2 text-sm">
              {formats[sourceKind].map((format) => <option key={format.kind} value={format.kind}>{format.label}</option>)}
            </select>
          </label>

          <button
            onClick={() => createExport.mutate()}
            disabled={!sourceId || createExport.isPending}
            className="mt-6 flex h-10 items-center justify-center gap-2 rounded-xl bg-ink px-4 text-sm text-panel disabled:opacity-40"
          >
            <FileDown size={15}/> Queue export
          </button>
        </div>
      </section>

      <section className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <div><h2 className="font-medium">Export history</h2><p className="mt-1 text-xs text-ink/45">Pending and processing jobs update automatically.</p></div>
          <button onClick={() => jobs.refetch()} className="rounded-xl border p-2" aria-label="Refresh exports"><RefreshCw size={15}/></button>
        </div>

        {jobs.isLoading ? (
          <div className="surface p-8 text-sm text-ink/45">Loading exports…</div>
        ) : jobs.isError ? (
          <div className="surface p-8 text-sm text-red-600">Could not load exports.</div>
        ) : jobs.data?.length ? (
          <div className="overflow-hidden rounded-2xl border bg-panel">
            <div className="divide-y">
              {jobs.data.map((job) => (
                <div key={job.id} className="flex flex-wrap items-center gap-3 p-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium">{job.filename || job.kind.replaceAll("_", " ")}</p>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                        job.status === "ready" ? "bg-emerald-500/10 text-emerald-700" :
                        job.status === "failed" ? "bg-red-500/10 text-red-700" :
                        "bg-amber-500/10 text-amber-700"
                      }`}>{job.status}</span>
                    </div>
                    <p className="mt-1 text-xs text-ink/40">{job.kind.replaceAll("_", " ")} · {new Date(job.created_at).toLocaleString()}</p>
                    {job.error_message && <p className="mt-2 text-xs text-red-600">{job.error_message}</p>}
                  </div>

                  {job.status === "ready" && (
                    <button onClick={() => void downloadExport(job)} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs hover:bg-muted">
                      <Download size={14}/>Download
                    </button>
                  )}
                  {job.status === "failed" && (
                    <button onClick={() => retryExport.mutate(job.id)} className="rounded-lg border p-2 hover:bg-muted" aria-label="Retry export"><RefreshCw size={14}/></button>
                  )}
                  <button onClick={() => deleteExport.mutate(job.id)} className="rounded-lg p-2 text-red-600 hover:bg-red-50" aria-label="Delete export"><Trash2 size={14}/></button>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="surface p-8 text-center text-sm text-ink/45">No exports yet.</div>
        )}
      </section>
    </div>
  );
}
