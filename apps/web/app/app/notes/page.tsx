"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type Note = {
  id: string;
  title: string;
  content_markdown: string;
  source_links: Array<Record<string, unknown>>;
  updated_at?: string;
};

export default function NotesPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const notes = useQuery({
    queryKey: ["notes", workspaceId],
    queryFn: () => api<Note[]>(`/notes?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const selected = notes.data?.find((note) => note.id === selectedId) ?? null;
  useEffect(() => {
    if (!selected) return;
    setTitle(selected.title);
    setContent(selected.content_markdown);
  }, [selected]);

  const createNote = useMutation({
    mutationFn: () => api<Note>("/notes", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId,
        title: "Untitled note",
        content_markdown: "",
        source_links: [],
      }),
    }),
    onSuccess: async (note) => {
      await queryClient.invalidateQueries({ queryKey: ["notes", workspaceId] });
      setSelectedId(note.id);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not create note"),
  });

  const saveNote = useMutation({
    mutationFn: () => api<Note>(`/notes/${selectedId}`, {
      method: "PATCH",
      body: JSON.stringify({ title: title.trim(), content_markdown: content }),
    }),
    onSuccess: async () => {
      toast.success("Note saved");
      await queryClient.invalidateQueries({ queryKey: ["notes", workspaceId] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not save note"),
  });

  const deleteNote = useMutation({
    mutationFn: () => api<void>(`/notes/${selectedId}`, { method: "DELETE" }),
    onSuccess: async () => {
      setSelectedId(null);
      setTitle("");
      setContent("");
      await queryClient.invalidateQueries({ queryKey: ["notes", workspaceId] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not delete note"),
  });

  if (!workspaceId) {
    return <div className="p-8 text-sm text-ink/50">Select or create a workspace to use notes.</div>;
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-[260px_1fr]">
      <aside className="min-h-0 border-e bg-panel p-3">
        <button
          onClick={() => createNote.mutate()}
          disabled={createNote.isPending}
          className="mb-3 flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-3 py-2 text-sm text-panel disabled:opacity-50"
        >
          <Plus size={15}/> New note
        </button>
        <div className="h-[calc(100%-48px)] space-y-1 overflow-auto">
          {notes.isLoading && <p className="px-2 py-4 text-sm text-ink/45">Loading notes…</p>}
          {notes.data?.map((note) => (
            <button
              key={note.id}
              onClick={() => setSelectedId(note.id)}
              className={`w-full rounded-xl px-3 py-2 text-left ${selectedId === note.id ? "bg-muted" : "hover:bg-muted/60"}`}
            >
              <p className="truncate text-sm font-medium">{note.title}</p>
              <p className="mt-1 line-clamp-2 text-xs text-ink/45">{note.content_markdown || "Empty note"}</p>
            </button>
          ))}
          {!notes.isLoading && notes.data?.length === 0 && <p className="px-2 py-8 text-center text-sm text-ink/45">No notes yet.</p>}
        </div>
      </aside>

      {!selected ? (
        <main className="grid place-items-center p-8 text-center">
          <div><h1 className="text-xl font-semibold">Notes</h1><p className="mt-2 text-sm text-ink/50">Select a note or create one to start writing.</p></div>
        </main>
      ) : (
        <main className="grid min-h-0 grid-rows-[auto_1fr]">
          <header className="flex items-center gap-3 border-b bg-panel p-3">
            <label className="sr-only" htmlFor="note-title">Note title</label>
            <input id="note-title" value={title} onChange={(event) => setTitle(event.target.value)} className="min-w-0 flex-1 bg-transparent text-lg font-semibold outline-none" />
            <button onClick={() => saveNote.mutate()} disabled={!title.trim() || saveNote.isPending} className="rounded-lg p-2 hover:bg-muted disabled:opacity-40" aria-label="Save note"><Save size={17}/></button>
            <button onClick={() => deleteNote.mutate()} disabled={deleteNote.isPending} className="rounded-lg p-2 text-red-600 hover:bg-red-50" aria-label="Delete note"><Trash2 size={17}/></button>
          </header>
          <div className="grid min-h-0 lg:grid-cols-2">
            <div className="min-h-0 border-e p-4">
              <label className="sr-only" htmlFor="note-content">Markdown note content</label>
              <textarea id="note-content" value={content} onChange={(event) => setContent(event.target.value)} className="h-full min-h-[360px] w-full resize-none bg-transparent text-sm leading-7 outline-none" placeholder="Write Markdown…" />
            </div>
            <article className="prose min-h-0 max-w-none overflow-auto p-6 text-sm dark:prose-invert">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || "_Nothing to preview yet._"}</ReactMarkdown>
            </article>
          </div>
        </main>
      )}
    </div>
  );
}
