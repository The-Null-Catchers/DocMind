"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus, MoreHorizontal, Pin, PinOff, Square, Trash2, Pencil, Library } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { api, apiResponse } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type DocumentRow = { id: string; title: string; status: string };
type Conversation = {
  id: string;
  title: string;
  pinned: boolean;
  updated_at?: string;
  document_ids: string[];
};
type Citation = {
  ordinal: number;
  chunk_id: string;
  document_id: string;
  page_number: number | null;
  source_excerpt: string;
};
type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  model?: string | null;
  citations: Citation[];
};

function parseSseBlock(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

export default function ChatsPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [sourceDialogOpen, setSourceDialogOpen] = useState(false);
  const [draftSources, setDraftSources] = useState<Set<string>>(new Set());
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const conversations = useQuery({
    queryKey: ["conversations", workspaceId],
    queryFn: () => api<Conversation[]>(`/conversations?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });
  const documents = useQuery({
    queryKey: ["documents", workspaceId],
    queryFn: () => api<DocumentRow[]>(`/documents?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const selected = useMemo(
    () => conversations.data?.find((conversation) => conversation.id === selectedId) ?? null,
    [conversations.data, selectedId],
  );

  useEffect(() => {
    if (selectedId || !conversations.data?.length) return;
    setSelectedId(conversations.data[0].id);
  }, [conversations.data, selectedId]);

  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    api<Message[]>(`/conversations/${selectedId}/messages`)
      .then((rows) => {
        if (!cancelled) setMessages(rows);
      })
      .catch((error) => {
        if (!cancelled) toast.error(error instanceof Error ? error.message : "Could not load conversation");
      });
    return () => { cancelled = true; };
  }, [selectedId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const createConversation = useMutation({
    mutationFn: () => api<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId,
        title: "New conversation",
        document_ids: [],
      }),
    }),
    onSuccess: async (conversation) => {
      await queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId] });
      setSelectedId(conversation.id);
      setMessages([]);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not create conversation"),
  });

  const patchConversation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Record<string, unknown> }) =>
      api<Conversation>(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not update conversation"),
  });

  const deleteConversation = useMutation({
    mutationFn: (id: string) => api<void>(`/conversations/${id}`, { method: "DELETE" }),
    onSuccess: async (_, id) => {
      if (selectedId === id) {
        setSelectedId(null);
        setMessages([]);
      }
      await queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not delete conversation"),
  });

  async function renameConversation(conversation: Conversation) {
    const next = window.prompt("Conversation title", conversation.title)?.trim();
    if (!next || next === conversation.title) return;
    patchConversation.mutate({ id: conversation.id, patch: { title: next } });
  }

  function openSources() {
    setDraftSources(new Set(selected?.document_ids ?? []));
    setSourceDialogOpen(true);
  }

  function saveSources() {
    if (!selected) return;
    patchConversation.mutate({
      id: selected.id,
      patch: { document_ids: Array.from(draftSources) },
    });
    setSourceDialogOpen(false);
  }

  async function sendMessage() {
    const text = query.trim();
    if (!text || !selected || sending) return;
    setQuery("");
    setSending(true);
    const assistant: Message = { role: "assistant", content: "", citations: [], status: "streaming" };
    setMessages((current) => [...current, { role: "user", content: text, citations: [] }, assistant]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await apiResponse(`/conversations/${selected.id}/messages/stream`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          message: text,
          document_ids: selected.document_ids,
          language: "auto",
        }),
        headers: { accept: "text/event-stream" },
      });
      if (!response.body) throw new Error("Streaming response unavailable");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantText = "";
      let citations: Citation[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const parsed = parseSseBlock(block);
          if (!parsed) continue;
          if (parsed.event === "token" && parsed.data && typeof parsed.data === "object" && "text" in parsed.data) {
            assistantText += String((parsed.data as { text: unknown }).text ?? "");
          } else if (parsed.event === "citations" && Array.isArray(parsed.data)) {
            citations = parsed.data as Citation[];
          } else if (parsed.event === "error") {
            throw new Error("Generation failed");
          }
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, content: assistantText, citations, status: "streaming" };
            }
            return next;
          });
        }
      }

      setMessages((current) => {
        const next = [...current];
        const last = next[next.length - 1];
        if (last?.role === "assistant") next[next.length - 1] = { ...last, content: assistantText, citations, status: "complete" };
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId] });
    } catch (error) {
      if ((error as DOMException)?.name !== "AbortError") {
        toast.error(error instanceof Error ? error.message : "Generation failed");
        setMessages((current) => {
          const next = [...current];
          const last = next[next.length - 1];
          if (last?.role === "assistant") next[next.length - 1] = { ...last, status: "failed" };
          return next;
        });
      }
    } finally {
      abortRef.current = null;
      setSending(false);
    }
  }

  if (!workspaceId) return <div className="p-8 text-sm text-ink/50">Select or create a workspace to start chatting.</div>;

  return (
    <div className="grid h-full min-h-0 grid-cols-[300px_1fr]">
      <aside className="min-h-0 border-e bg-panel p-3">
        <button
          onClick={() => createConversation.mutate()}
          disabled={createConversation.isPending}
          className="mb-3 flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-3 py-2 text-sm text-panel disabled:opacity-50"
        >
          <MessageSquarePlus size={16}/> New chat
        </button>
        <div className="h-[calc(100%-48px)] overflow-auto">
          {conversations.isLoading && <p className="px-2 py-4 text-sm text-ink/45">Loading conversations…</p>}
          {conversations.data?.map((conversation) => (
            <div key={conversation.id} className={`group mb-1 flex items-center rounded-xl ${selectedId === conversation.id ? "bg-muted" : "hover:bg-muted/60"}`}>
              <button onClick={() => setSelectedId(conversation.id)} className="min-w-0 flex-1 px-3 py-2 text-left">
                <div className="flex items-center gap-1.5"><p className="truncate text-sm font-medium">{conversation.title}</p>{conversation.pinned && <Pin size={11}/>}</div>
                <p className="mt-1 text-xs text-ink/40">{conversation.document_ids.length ? `${conversation.document_ids.length} sources` : "Workspace context"}</p>
              </button>
              <details className="relative me-1">
                <summary className="list-none rounded-lg p-2 text-ink/45 hover:bg-panel"><MoreHorizontal size={15}/></summary>
                <div className="absolute end-0 z-20 w-44 rounded-xl border bg-panel p-1 shadow-soft">
                  <button onClick={() => renameConversation(conversation)} className="flex w-full gap-2 rounded-lg px-2 py-2 text-sm hover:bg-muted"><Pencil size={14}/>Rename</button>
                  <button onClick={() => patchConversation.mutate({ id: conversation.id, patch: { pinned: !conversation.pinned } })} className="flex w-full gap-2 rounded-lg px-2 py-2 text-sm hover:bg-muted">{conversation.pinned ? <PinOff size={14}/> : <Pin size={14}/>} {conversation.pinned ? "Unpin" : "Pin"}</button>
                  <button onClick={() => deleteConversation.mutate(conversation.id)} className="flex w-full gap-2 rounded-lg px-2 py-2 text-sm text-red-600 hover:bg-red-50"><Trash2 size={14}/>Delete</button>
                </div>
              </details>
            </div>
          ))}
          {!conversations.isLoading && conversations.data?.length === 0 && <p className="px-3 py-8 text-center text-sm text-ink/45">No conversations yet.</p>}
        </div>
      </aside>

      {!selected ? (
        <main className="grid place-items-center p-8 text-center"><div><h1 className="text-xl font-semibold">Ask DocMind</h1><p className="mt-2 text-sm text-ink/50">Start a conversation grounded in your authorized workspace documents.</p></div></main>
      ) : (
        <main className="flex min-h-0 flex-col">
          <header className="flex h-14 items-center gap-3 border-b bg-panel px-4">
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{selected.title}</p><p className="text-xs text-ink/40">{selected.document_ids.length ? `${selected.document_ids.length} selected documents` : "All workspace documents"}</p></div>
            <button onClick={openSources} className="flex items-center gap-2 rounded-xl border px-3 py-2 text-xs hover:bg-muted"><Library size={14}/>Sources</button>
          </header>
          <div className="min-h-0 flex-1 overflow-auto p-5">
            <div className="mx-auto max-w-3xl space-y-5">
              {messages.length === 0 && <div className="py-16 text-center"><p className="font-medium">Ask a question about your documents</p><p className="mt-1 text-sm text-ink/45">Answers use server-validated source citations.</p></div>}
              {messages.map((message, index) => (
                <div key={message.id ?? index} className={message.role === "user" ? "ms-auto max-w-[82%] rounded-2xl bg-ink px-4 py-3 text-sm text-panel" : "max-w-[94%]"}>
                  {message.role === "assistant" ? <article className="text-sm leading-7"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || (message.status === "streaming" ? "…" : "")}</ReactMarkdown></article> : message.content}
                  {message.role === "assistant" && message.citations.length > 0 && <div className="mt-3 space-y-2">{message.citations.map((citation) => (
                    <Link key={`${citation.chunk_id}-${citation.ordinal}`} href={`/app/documents/${citation.document_id}?page=${citation.page_number ?? 1}&chunk=${encodeURIComponent(citation.chunk_id)}`} className="block rounded-xl border p-3 hover:bg-muted/40">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/45">Source {citation.ordinal}{citation.page_number ? ` · Page ${citation.page_number}` : ""}</p>
                      <p className="mt-1 line-clamp-3 text-xs leading-5 text-ink/60">{citation.source_excerpt}</p>
                    </Link>
                  ))}</div>}
                  {message.status === "failed" && <p className="mt-2 text-xs text-red-600">Generation failed. Your question remains in history.</p>}
                </div>
              ))}
              <div ref={bottomRef}/>
            </div>
          </div>
          <div className="border-t bg-panel p-3">
            <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border bg-muted/20 p-2">
              <textarea value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendMessage(); } }} rows={2} placeholder="Ask across this conversation’s sources…" className="min-h-12 flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none"/>
              {sending ? <button onClick={() => abortRef.current?.abort()} className="grid h-9 w-9 place-items-center rounded-xl border" aria-label="Stop generation"><Square size={14}/></button> : <button onClick={() => void sendMessage()} disabled={!query.trim()} className="rounded-xl bg-ink px-4 py-2 text-sm text-panel disabled:opacity-40">Send</button>}
            </div>
          </div>
        </main>
      )}

      {sourceDialogOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" role="dialog" aria-modal="true" aria-label="Conversation sources">
        <div className="w-full max-w-lg rounded-2xl border bg-panel p-5 shadow-soft">
          <h2 className="text-lg font-semibold">Conversation sources</h2>
          <p className="mt-1 text-sm text-ink/45">Select specific ready documents. Leave everything unchecked to use workspace context.</p>
          <div className="mt-4 max-h-[50vh] space-y-1 overflow-auto">
            {documents.data?.map((document) => <label key={document.id} className="flex items-center gap-3 rounded-xl p-2 hover:bg-muted">
              <input type="checkbox" disabled={document.status !== "ready"} checked={draftSources.has(document.id)} onChange={(event) => setDraftSources((current) => { const next = new Set(current); if (event.target.checked) next.add(document.id); else next.delete(document.id); return next; })}/>
              <span className="min-w-0 flex-1 truncate text-sm">{document.title}</span>
              <span className="text-xs text-ink/35">{document.status}</span>
            </label>)}
          </div>
          <div className="mt-5 flex justify-end gap-2"><button onClick={() => setSourceDialogOpen(false)} className="rounded-xl border px-4 py-2 text-sm">Cancel</button><button onClick={saveSources} className="rounded-xl bg-ink px-4 py-2 text-sm text-panel">Apply</button></div>
        </div>
      </div>}
    </div>
  );
}
