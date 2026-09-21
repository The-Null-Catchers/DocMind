"use client";

import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText, MessageSquareText, NotebookPen, Search, Brain } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type SearchMode = "keyword" | "exact" | "semantic" | "hybrid";
type ContentType =
  | "documents"
  | "document_content"
  | "conversations"
  | "notes"
  | "flashcards";

type DocumentRow = {
  id: string;
  title: string;
  mime_type: string;
  folder_id: string | null;
};
type Folder = { id: string; name: string };
type Tag = { id: string; name: string };
type SearchResult = {
  type: "document" | "document_content" | "conversation" | "note" | "flashcard";
  id: string;
  title: string;
  excerpt: string;
  score: number;
  document_id: string | null;
  page_number: number | null;
  chunk_id: string | null;
};

const contentTypeOptions: Array<{ value: ContentType; label: string }> = [
  { value: "documents", label: "Documents" },
  { value: "document_content", label: "Document content" },
  { value: "conversations", label: "Conversations" },
  { value: "notes", label: "Notes" },
  { value: "flashcards", label: "Flashcards" },
];

function resultIcon(type: SearchResult["type"]) {
  if (type === "conversation") return MessageSquareText;
  if (type === "note") return NotebookPen;
  if (type === "flashcard") return Brain;
  return FileText;
}

function resultHref(result: SearchResult) {
  if (result.type === "document" || result.type === "document_content") {
    const params = new URLSearchParams();
    if (result.page_number) params.set("page", String(result.page_number));
    if (result.chunk_id) params.set("chunk", result.chunk_id);
    const suffix = params.toString();
    return `/app/documents/${result.document_id}${suffix ? `?${suffix}` : ""}`;
  }
  if (result.type === "conversation") return `/app/chats?conversation=${encodeURIComponent(result.id)}`;
  if (result.type === "note") return `/app/notes?note=${encodeURIComponent(result.id)}`;
  return "/app/flashcards";
}

export default function SearchPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [contentTypes, setContentTypes] = useState<Set<ContentType>>(
    new Set(contentTypeOptions.map((option) => option.value)),
  );
  const [documentIds, setDocumentIds] = useState<string[]>([]);
  const [folderId, setFolderId] = useState("");
  const [mimeTypes, setMimeTypes] = useState<string[]>([]);
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [createdAfter, setCreatedAfter] = useState("");
  const [createdBefore, setCreatedBefore] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const documents = useQuery({
    queryKey: ["documents", workspaceId],
    queryFn: () => api<DocumentRow[]>(`/documents?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });
  const folders = useQuery({
    queryKey: ["folders", workspaceId],
    queryFn: () => api<Folder[]>(`/folders?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });
  const tags = useQuery({
    queryKey: ["tags", workspaceId],
    queryFn: () => api<Tag[]>(`/tags?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const search = useQuery({
    queryKey: [
      "global-search",
      workspaceId,
      submittedQuery,
      mode,
      Array.from(contentTypes).sort().join(","),
      documentIds.join(","),
      folderId,
      mimeTypes.join(","),
      tagIds.join(","),
      createdAfter,
      createdBefore,
    ],
    queryFn: () =>
      api<SearchResult[]>("/search/global", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: workspaceId,
          query: submittedQuery,
          mode,
          content_types: Array.from(contentTypes),
          document_ids: documentIds,
          folder_id: folderId || null,
          mime_types: mimeTypes,
          tag_ids: tagIds,
          created_after: createdAfter ? new Date(`${createdAfter}T00:00:00`).toISOString() : null,
          created_before: createdBefore ? new Date(`${createdBefore}T23:59:59`).toISOString() : null,
          limit: 60,
        }),
      }),
    enabled: Boolean(workspaceId && submittedQuery),
  });

  const mimeOptions = useMemo(
    () => Array.from(new Set((documents.data ?? []).map((document) => document.mime_type))).sort(),
    [documents.data],
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (!value || contentTypes.size === 0) return;
    setSubmittedQuery(value);
  }

  function toggleContentType(value: ContentType) {
    setContentTypes((current) => {
      const next = new Set(current);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  if (!workspaceId) {
    return <div className="p-8 text-sm text-ink/50">Select a workspace to search.</div>;
  }

  return (
    <div className="grid h-full min-h-0 lg:grid-cols-[310px_1fr]">
      <aside className="min-h-0 overflow-auto border-e bg-panel p-4">
        <h1 className="text-xl font-semibold">Search</h1>
        <p className="mt-1 text-xs leading-5 text-ink/45">
          Search authorized workspace content across documents, chats, notes, and study material.
        </p>

        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Content types</p>
          <div className="mt-2 space-y-1">
            {contentTypeOptions.map((option) => (
              <label key={option.value} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-muted">
                <input
                  type="checkbox"
                  checked={contentTypes.has(option.value)}
                  onChange={() => toggleContentType(option.value)}
                />
                {option.label}
              </label>
            ))}
          </div>
        </div>

        <label className="mt-5 block text-xs font-medium">Folder
          <select value={folderId} onChange={(event) => setFolderId(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2 text-sm">
            <option value="">All folders</option>
            {folders.data?.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
          </select>
        </label>

        <label className="mt-4 block text-xs font-medium">Documents
          <select
            multiple
            value={documentIds}
            onChange={(event) => setDocumentIds(Array.from(event.target.selectedOptions, (option) => option.value))}
            className="mt-2 min-h-28 w-full rounded-xl border bg-panel px-2 py-2 text-sm"
          >
            {documents.data?.map((document) => <option key={document.id} value={document.id}>{document.title}</option>)}
          </select>
        </label>

        <label className="mt-4 block text-xs font-medium">File types
          <select
            multiple
            value={mimeTypes}
            onChange={(event) => setMimeTypes(Array.from(event.target.selectedOptions, (option) => option.value))}
            className="mt-2 min-h-20 w-full rounded-xl border bg-panel px-2 py-2 text-sm"
          >
            {mimeOptions.map((mime) => <option key={mime} value={mime}>{mime}</option>)}
          </select>
        </label>

        <label className="mt-4 block text-xs font-medium">Tags
          <select
            multiple
            value={tagIds}
            onChange={(event) => setTagIds(Array.from(event.target.selectedOptions, (option) => option.value))}
            className="mt-2 min-h-20 w-full rounded-xl border bg-panel px-2 py-2 text-sm"
          >
            {tags.data?.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
          </select>
        </label>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <label className="text-xs font-medium">From
            <input type="date" value={createdAfter} onChange={(event) => setCreatedAfter(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-2 py-2 text-xs"/>
          </label>
          <label className="text-xs font-medium">To
            <input type="date" value={createdBefore} onChange={(event) => setCreatedBefore(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-2 py-2 text-xs"/>
          </label>
        </div>
      </aside>

      <main className="min-h-0 overflow-auto p-6 lg:p-8">
        <form onSubmit={submit} className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="flex min-w-0 flex-1 items-center gap-2 rounded-2xl border bg-panel px-4">
              <Search size={18} className="text-ink/40"/>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search your workspace…"
                className="h-12 min-w-0 flex-1 bg-transparent text-sm outline-none"
              />
            </div>
            <select value={mode} onChange={(event) => setMode(event.target.value as SearchMode)} className="rounded-xl border bg-panel px-3 py-2 text-sm">
              <option value="hybrid">Hybrid</option>
              <option value="semantic">Semantic</option>
              <option value="keyword">Keyword</option>
              <option value="exact">Exact phrase</option>
            </select>
            <button disabled={!query.trim() || contentTypes.size === 0} className="rounded-xl bg-ink px-5 py-2 text-sm font-medium text-panel disabled:opacity-40">Search</button>
          </div>
        </form>

        <div className="mx-auto mt-6 max-w-5xl">
          {!submittedQuery && (
            <div className="surface p-8 text-center">
              <p className="font-medium">Search across your knowledge workspace</p>
              <p className="mt-2 text-sm text-ink/45">Use hybrid search for the best balance of meaning and exact terms.</p>
            </div>
          )}
          {search.isLoading && <div className="surface p-8 text-sm text-ink/45">Searching…</div>}
          {search.isError && <div className="surface p-8 text-sm text-red-600">Search failed. Try again.</div>}
          {search.data && (
            <div>
              <div className="mb-3 flex items-center justify-between text-xs text-ink/45">
                <span>{search.data.length} results for “{submittedQuery}”</span>
                <span className="capitalize">{mode} mode</span>
              </div>
              <div className="space-y-2">
                {search.data.map((result) => {
                  const Icon = resultIcon(result.type);
                  return (
                    <Link key={`${result.type}-${result.id}`} href={resultHref(result)} className="surface block p-4 hover:bg-muted/35">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 rounded-lg bg-muted p-2"><Icon size={16}/></div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate font-medium">{result.title}</p>
                            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide text-ink/45">{result.type.replace("_", " ")}</span>
                            {result.page_number && <span className="text-[11px] text-ink/40">Page {result.page_number}</span>}
                          </div>
                          <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-ink/60">{result.excerpt}</p>
                        </div>
                      </div>
                    </Link>
                  );
                })}
                {search.data.length === 0 && (
                  <div className="surface p-8 text-center text-sm text-ink/45">No results matched these filters.</div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
