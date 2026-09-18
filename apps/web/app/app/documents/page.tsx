"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, FileText, Loader2, RefreshCw, RotateCcw, Search, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type DocumentRow = {
  id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  status: string;
  processing_progress: number;
  page_count: number | null;
  error_message?: string | null;
};

export default function DocumentsPage() {
  const workspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  useEffect(() => {
    if (window.location.hash === "#upload") {
      input.current?.click();
      history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  const documents = useQuery({
    queryKey: ["documents", workspaceId],
    queryFn: () => api<DocumentRow[]>(`/documents?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
    refetchInterval: (query) => query.state.data?.some((doc) => !["ready", "failed"].includes(doc.status)) ? 3000 : false,
  });

  const reprocess = useMutation({
    mutationFn: (id: string) => api(`/documents/${id}/reprocess`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", workspaceId] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not reprocess document"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api(`/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", workspaceId] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not delete document"),
  });

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return documents.data ?? [];
    return (documents.data ?? []).filter((doc) => `${doc.title} ${doc.original_filename}`.toLowerCase().includes(needle));
  }, [documents.data, search]);

  async function uploadFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!workspaceId || files.length === 0) return;
    setUploading(true);
    setUploadProgress(0);
    try {
      for (let index = 0; index < files.length; index += 1) {
        const form = new FormData();
        form.append("workspace_id", workspaceId);
        form.append("file", files[index]);
        await api("/documents/upload", { method: "POST", body: form });
        setUploadProgress(((index + 1) / files.length) * 100);
      }
      toast.success(files.length === 1 ? "Document uploaded" : `${files.length} documents uploaded`);
      await queryClient.invalidateQueries({ queryKey: ["documents", workspaceId] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  if (!workspaceId) {
    return <div className="p-6 lg:p-8"><h1 className="text-2xl font-semibold">Documents</h1><div className="surface mt-6 p-8 text-sm text-ink/55">Create or select a workspace to upload documents.</div></div>;
  }

  return <div className="p-6 lg:p-8">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-2xl font-semibold tracking-tight">Documents</h1><p className="mt-1 text-sm text-ink/50">Upload, process, search, and open your workspace sources.</p></div>
      <div className="flex gap-2">
        <button onClick={()=>documents.refetch()} disabled={documents.isFetching} className="rounded-xl border bg-panel p-2.5" aria-label="Refresh documents"><RefreshCw size={16} className={documents.isFetching ? "animate-spin" : ""}/></button>
        <button disabled={uploading} onClick={()=>input.current?.click()} className="flex items-center gap-2 rounded-xl bg-ink px-4 py-2 text-sm text-panel disabled:opacity-60"><Upload size={16}/>{uploading ? "Uploading…" : "Upload documents"}</button>
        <input ref={input} className="hidden" type="file" multiple accept=".pdf,.docx,.pptx,.txt,.md,.csv,image/*" onChange={uploadFiles}/>
      </div>
    </div>
    {uploading && <div className="mt-4"><div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-accent transition-all" style={{width:`${uploadProgress}%`}}/></div><p className="mt-1 text-xs text-ink/45">Uploaded {Math.round(uploadProgress)}%</p></div>}
    <label className="mt-6 flex max-w-xl items-center gap-2 rounded-xl border bg-panel px-3 py-2.5 text-sm"><Search size={16} className="text-ink/40"/><input value={search} onChange={(event)=>setSearch(event.target.value)} placeholder="Search documents…" className="w-full bg-transparent outline-none"/></label>

    {documents.isLoading ? <div className="grid place-items-center py-20"><Loader2 className="animate-spin text-ink/40"/></div> : documents.isError ? (
      <div className="surface mt-5 flex items-center gap-3 p-5 text-sm"><CircleAlert className="text-red-500" size={18}/><span>Could not load documents.</span><button onClick={()=>documents.refetch()} className="ms-auto underline">Retry</button></div>
    ) : visible.length === 0 ? (
      <div className="surface mt-5 p-10 text-center"><FileText className="mx-auto text-ink/25" size={34}/><h2 className="mt-4 font-medium">{search ? "No matching documents" : "No documents yet"}</h2><p className="mt-1 text-sm text-ink/45">{search ? "Try another search term." : "Upload a PDF, Office file, text file, CSV, or image to begin."}</p>{!search && <button onClick={()=>input.current?.click()} className="mt-5 rounded-xl bg-ink px-4 py-2 text-sm text-panel">Upload first document</button>}</div>
    ) : (
      <div className="mt-5 overflow-hidden rounded-2xl border bg-panel">
        <div className="grid grid-cols-[minmax(0,1fr)_140px_120px_90px] border-b bg-muted/30 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink/40"><span>Name</span><span>Type</span><span>Status</span><span className="text-end">Actions</span></div>
        {visible.map((doc)=><div key={doc.id} className="grid grid-cols-[minmax(0,1fr)_140px_120px_90px] items-center border-b px-4 py-3.5 last:border-0 hover:bg-muted/25">
          <Link href={`/app/documents/${doc.id}`} className="flex min-w-0 items-center gap-3"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted"><FileText size={17}/></div><div className="min-w-0"><p className="truncate text-sm font-medium">{doc.title || doc.original_filename}</p><p className="text-xs text-ink/40">{doc.page_count ? `${doc.page_count} pages · ` : ""}{formatBytes(doc.file_size)}</p></div></Link>
          <span className="truncate text-xs text-ink/50">{doc.mime_type}</span>
          <span className="flex items-center gap-1.5 text-xs">{doc.status === "ready" ? <CircleCheck size={14} className="text-emerald-500"/> : doc.status === "failed" ? <CircleAlert size={14} className="text-red-500"/> : <Loader2 size={14} className="animate-spin text-amber-500"/>}<span>{doc.status === "ready" ? "Ready" : doc.status === "failed" ? "Failed" : `${doc.processing_progress ?? 0}%`}</span></span>
          <div className="flex justify-end gap-1">{doc.status !== "ready" && <button onClick={()=>reprocess.mutate(doc.id)} className="rounded-lg p-2 hover:bg-muted" title="Reprocess"><RotateCcw size={15}/></button>}<button onClick={()=>{if(confirm(`Delete ${doc.title || doc.original_filename}?`)) remove.mutate(doc.id)}} className="rounded-lg p-2 hover:bg-muted" title="Delete"><Trash2 size={15}/></button></div>
        </div>)}
      </div>
    )}
  </div>;
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
