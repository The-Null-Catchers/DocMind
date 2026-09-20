"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownAZ,
  ArrowUpAZ,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  FileText,
  FolderOpen,
  Loader2,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type DocumentRow = {
  id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  folder_id: string | null;
  status: string;
  processing_progress: number;
  page_count: number | null;
  error_message?: string | null;
  created_at: string;
};

type LibraryResponse = {
  items: DocumentRow[];
  total: number;
  offset: number;
  limit: number;
  facets: {
    statuses: string[];
    mime_types: string[];
  };
};

type Folder = { id: string; name: string; parent_id: string | null };

const PAGE_SIZE = 25;

export default function DocumentsPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("");
  const [mimeType, setMimeType] = useState("");
  const [folderId, setFolderId] = useState("");
  const [sort, setSort] = useState<"created_at" | "title" | "file_size" | "status">("created_at");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (window.location.hash === "#upload") {
      input.current?.click();
      history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(0);
  }, [debouncedSearch, status, mimeType, folderId, sort, direction, workspaceId]);

  const queryString = new URLSearchParams({
    workspace_id: workspaceId ?? "",
    q: debouncedSearch,
    sort,
    direction,
    offset: String(page * PAGE_SIZE),
    limit: String(PAGE_SIZE),
  });
  if (status) queryString.set("status", status);
  if (mimeType) queryString.set("mime_type", mimeType);
  if (folderId) queryString.set("folder_id", folderId);

  const documents = useQuery({
    queryKey: ["document-library", workspaceId, debouncedSearch, status, mimeType, folderId, sort, direction, page],
    queryFn: () => api<LibraryResponse>(`/documents/library?${queryString.toString()}`),
    enabled: Boolean(workspaceId),
    refetchInterval: (query) => query.state.data?.items.some((document) => !["ready", "failed"].includes(document.status)) ? 3000 : false,
  });

  const folders = useQuery({
    queryKey: ["folders", workspaceId],
    queryFn: () => api<Folder[]>(`/folders?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const invalidateDocuments = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["document-library", workspaceId] }),
      queryClient.invalidateQueries({ queryKey: ["documents", workspaceId] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard", workspaceId] }),
    ]);
  };

  const reprocess = useMutation({
    mutationFn: (id: string) => api(`/documents/${id}/reprocess`, { method: "POST" }),
    onSuccess: invalidateDocuments,
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not reprocess document"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api(`/documents/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      if (documents.data?.items.length === 1 && page > 0) setPage((current) => current - 1);
      await invalidateDocuments();
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not delete document"),
  });

  async function uploadSelectedFiles(files: File[]) {
    if (!workspaceId || files.length === 0 || uploading) return;
    setUploading(true);
    setUploadProgress(0);
    let completed = 0;
    let failed = 0;
    for (const file of files) {
      try {
        const form = new FormData();
        form.append("workspace_id", workspaceId);
        if (folderId) form.append("folder_id", folderId);
        form.append("file", file);
        await api("/documents/upload", { method: "POST", body: form });
      } catch (error) {
        failed += 1;
        toast.error(`${file.name}: ${error instanceof Error ? error.message : "Upload failed"}`);
      } finally {
        completed += 1;
        setUploadProgress((completed / files.length) * 100);
      }
    }

    const succeeded = files.length - failed;
    if (succeeded > 0) {
      toast.success(succeeded === 1 ? "Document uploaded" : `${succeeded} documents uploaded`);
      await invalidateDocuments();
    }
    setUploading(false);
  }

  function uploadFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    void uploadSelectedFiles(files);
  }

  function dropFiles(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void uploadSelectedFiles(Array.from(event.dataTransfer.files));
  }

  if (!workspaceId) {
    return <div className="p-6 lg:p-8"><h1 className="text-2xl font-semibold">Documents</h1><div className="surface mt-6 p-8 text-sm text-ink/55">Create or select a workspace to upload documents.</div></div>;
  }

  const totalPages = Math.max(1, Math.ceil((documents.data?.total ?? 0) / PAGE_SIZE));
  const items = documents.data?.items ?? [];

  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
          <p className="mt-1 text-sm text-ink/50">Upload, process, filter, and open workspace sources.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => documents.refetch()} disabled={documents.isFetching} className="focus-ring rounded-xl border bg-panel p-2.5" aria-label="Refresh documents"><RefreshCw size={16} className={documents.isFetching ? "animate-spin" : ""}/></button>
          <button disabled={uploading} onClick={() => input.current?.click()} className="focus-ring flex items-center gap-2 rounded-xl bg-ink px-4 py-2 text-sm text-panel disabled:opacity-60"><Upload size={16}/>{uploading ? "Uploading…" : "Upload documents"}</button>
          <input ref={input} className="hidden" type="file" multiple accept=".pdf,.docx,.pptx,.txt,.md,.csv,image/*" onChange={uploadFiles}/>
        </div>
      </div>

      <div
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={(event) => { if (event.currentTarget === event.target) setDragging(false); }}
        onDrop={dropFiles}
        className={`mt-5 rounded-2xl border border-dashed p-5 transition ${dragging ? "border-accent bg-accent/5" : "bg-panel"}`}
      >
        <div className="flex flex-wrap items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-muted"><Upload size={18}/></div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{dragging ? "Drop files to upload" : "Drag files here or use Upload documents"}</p>
            <p className="mt-0.5 text-xs text-ink/45">PDF, Office, text, CSV, Markdown, and supported images. {folderId ? "Uploads will use the selected folder." : ""}</p>
          </div>
          {uploading && <span className="text-xs text-ink/50">{Math.round(uploadProgress)}%</span>}
        </div>
        {uploading && <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-accent transition-all" style={{ width: `${uploadProgress}%` }}/></div>}
      </div>

      <div className="mt-5 grid gap-3 xl:grid-cols-[minmax(240px,1fr)_180px_220px_200px_150px]">
        <label className="flex items-center gap-2 rounded-xl border bg-panel px-3 py-2.5 text-sm">
          <Search size={16} className="text-ink/40"/>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents…" className="w-full bg-transparent outline-none"/>
        </label>
        <select aria-label="Status filter" value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none">
          <option value="">All statuses</option>
          {documents.data?.facets.statuses.map((value) => <option key={value} value={value}>{labelStatus(value)}</option>)}
        </select>
        <select aria-label="File type filter" value={mimeType} onChange={(event) => setMimeType(event.target.value)} className="rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none">
          <option value="">All file types</option>
          {documents.data?.facets.mime_types.map((value) => <option key={value} value={value}>{labelMime(value)}</option>)}
        </select>
        <select aria-label="Folder filter" value={folderId} onChange={(event) => setFolderId(event.target.value)} className="rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none">
          <option value="">All folders</option>
          {folders.data?.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
        </select>
        <div className="flex rounded-xl border bg-panel">
          <select aria-label="Sort documents" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="min-w-0 flex-1 bg-transparent px-3 py-2.5 text-sm outline-none">
            <option value="created_at">Date</option>
            <option value="title">Name</option>
            <option value="file_size">Size</option>
            <option value="status">Status</option>
          </select>
          <button onClick={() => setDirection((value) => value === "asc" ? "desc" : "asc")} className="focus-ring border-s px-3" aria-label={direction === "asc" ? "Sort descending" : "Sort ascending"} title={direction === "asc" ? "Ascending" : "Descending"}>
            {direction === "asc" ? <ArrowDownAZ size={16}/> : <ArrowUpAZ size={16}/>}
          </button>
        </div>
      </div>

      {documents.isLoading ? (
        <div className="grid place-items-center py-20"><Loader2 className="animate-spin text-ink/40"/></div>
      ) : documents.isError ? (
        <div className="surface mt-5 flex items-center gap-3 p-5 text-sm"><CircleAlert className="text-red-500" size={18}/><span>Could not load documents.</span><button onClick={() => documents.refetch()} className="ms-auto underline">Retry</button></div>
      ) : items.length === 0 ? (
        <div className="surface mt-5 p-10 text-center">
          <FileText className="mx-auto text-ink/25" size={34}/>
          <h2 className="mt-4 font-medium">{debouncedSearch || status || mimeType || folderId ? "No matching documents" : "No documents yet"}</h2>
          <p className="mt-1 text-sm text-ink/45">{debouncedSearch || status || mimeType || folderId ? "Change or clear one of the filters." : "Upload a PDF, Office file, text file, CSV, or image to begin."}</p>
          {!debouncedSearch && !status && !mimeType && !folderId && <button onClick={() => input.current?.click()} className="mt-5 rounded-xl bg-ink px-4 py-2 text-sm text-panel">Upload first document</button>}
        </div>
      ) : (
        <>
          <div className="mt-5 overflow-hidden rounded-2xl border bg-panel">
            <div className="grid grid-cols-[minmax(0,1fr)_150px_120px_120px_90px] border-b bg-muted/30 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink/40">
              <span>Name</span><span>Type</span><span>Status</span><span>Uploaded</span><span className="text-end">Actions</span>
            </div>
            {items.map((document) => (
              <div key={document.id} className="grid grid-cols-[minmax(0,1fr)_150px_120px_120px_90px] items-center border-b px-4 py-3.5 last:border-0 hover:bg-muted/25">
                <Link href={`/app/documents/${document.id}`} className="flex min-w-0 items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted"><FileText size={17}/></div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{document.title || document.original_filename}</p>
                    <p className="truncate text-xs text-ink/40">{document.page_count ? `${document.page_count} pages · ` : ""}{formatBytes(document.file_size)}{document.error_message ? ` · ${document.error_message}` : ""}</p>
                  </div>
                </Link>
                <span className="truncate text-xs text-ink/50" title={document.mime_type}>{labelMime(document.mime_type)}</span>
                <DocumentStatus document={document}/>
                <span className="text-xs text-ink/45">{formatDate(document.created_at)}</span>
                <div className="flex justify-end gap-1">
                  {document.status !== "ready" && <button onClick={() => reprocess.mutate(document.id)} disabled={reprocess.isPending} className="focus-ring rounded-lg p-2 hover:bg-muted disabled:opacity-40" title="Reprocess"><RotateCcw size={15}/></button>}
                  <button onClick={() => { if (confirm(`Delete ${document.title || document.original_filename}?`)) remove.mutate(document.id); }} disabled={remove.isPending} className="focus-ring rounded-lg p-2 hover:bg-muted disabled:opacity-40" title="Delete"><Trash2 size={15}/></button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-ink/50">
            <span>{documents.data?.total ?? 0} documents · page {page + 1} of {totalPages}</span>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage((value) => Math.max(0, value - 1))} disabled={page === 0} className="focus-ring flex items-center gap-1 rounded-xl border bg-panel px-3 py-2 disabled:opacity-35"><ChevronLeft size={15}/>Previous</button>
              <button onClick={() => setPage((value) => Math.min(totalPages - 1, value + 1))} disabled={page + 1 >= totalPages} className="focus-ring flex items-center gap-1 rounded-xl border bg-panel px-3 py-2 disabled:opacity-35">Next<ChevronRight size={15}/></button>
            </div>
          </div>
        </>
      )}

      {folders.data?.length ? (
        <p className="mt-5 flex items-center gap-1.5 text-xs text-ink/35"><FolderOpen size={13}/>Folder filtering and upload targeting use the workspace folder records stored by DocMind.</p>
      ) : null}
    </div>
  );
}

function DocumentStatus({ document }: { document: DocumentRow }) {
  if (document.status === "ready") return <span className="flex items-center gap-1.5 text-xs"><CircleCheck size={14} className="text-emerald-500"/>Ready</span>;
  if (document.status === "failed") return <span className="flex items-center gap-1.5 text-xs text-red-600"><CircleAlert size={14}/>Failed</span>;
  return <span className="flex items-center gap-1.5 text-xs"><Loader2 size={14} className="animate-spin text-amber-500"/>{document.processing_progress ?? 0}%</span>;
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(date);
}

function labelMime(value: string) {
  const known: Record<string, string> = {
    "application/pdf": "PDF",
    "text/plain": "Text",
    "text/markdown": "Markdown",
    "text/csv": "CSV",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
  };
  if (known[value]) return known[value];
  if (value.startsWith("image/")) return value.slice(6).toUpperCase();
  return value;
}

function labelStatus(value: string) {
  return value ? value[0].toUpperCase() + value.slice(1) : value;
}
