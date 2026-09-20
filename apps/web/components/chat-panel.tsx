"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp, Copy, Square, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { api, apiResponse } from "@/lib/api";

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
  citations: Citation[];
};

type Conversation = { id: string; title: string };

export function ChatPanel({
  workspaceId,
  documentId,
  documentTitle,
  onCitation,
}: {
  workspaceId: string;
  documentId: string;
  documentTitle: string;
  onCitation?: (citation: Citation) => void;
}) {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const storageKey = `docmind_document_chat_${documentId}`;

  useEffect(() => {
    let cancelled = false;
    async function restore() {
      setLoading(true);
      const saved = localStorage.getItem(storageKey);
      if (!saved) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const history = await api<Message[]>(`/conversations/${saved}/messages`);
        if (cancelled) return;
        setConversationId(saved);
        setMessages(history);
      } catch {
        localStorage.removeItem(storageKey);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    restore();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [storageKey]);

  async function ensureConversation() {
    if (conversationId) return conversationId;
    const created = await api<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({
        workspace_id: workspaceId,
        title: `Ask · ${documentTitle}`.slice(0, 240),
        document_ids: [documentId],
      }),
    });
    setConversationId(created.id);
    localStorage.setItem(storageKey, created.id);
    return created.id;
  }

  async function send() {
    const prompt = query.trim();
    if (!prompt || sending) return;
    setQuery("");
    setSending(true);
    const userMessage: Message = { role: "user", content: prompt, citations: [] };
    const assistantMessage: Message = { role: "assistant", content: "", citations: [], status: "retrieving" };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const id = await ensureConversation();
      const response = await apiResponse(`/conversations/${id}/messages/stream`, {
        method: "POST",
        signal: controller.signal,
        headers: { accept: "text/event-stream" },
        body: JSON.stringify({ message: prompt, document_ids: [documentId], language: "auto" }),
      });
      if (!response.body) throw new Error("Streaming response unavailable");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventName = "message";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const rawLine of lines) {
          const line = rawLine.trimEnd();
          if (line.startsWith("event:")) {
            eventName = line.slice(6).trim();
            continue;
          }
          if (!line.startsWith("data:")) continue;
          const rawData = line.slice(5).trim();
          if (!rawData) continue;
          const data = JSON.parse(rawData) as Record<string, unknown> | Citation[];
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            if (!last || last.role !== "assistant") return current;
            const updated = { ...last, citations: [...last.citations] };
            if (eventName === "token" && !Array.isArray(data)) updated.content += String(data.text ?? "");
            if (eventName === "status" && !Array.isArray(data)) updated.status = String(data.status ?? "generating");
            if (eventName === "citations" && Array.isArray(data)) updated.citations = data;
            if (eventName === "done" && !Array.isArray(data)) {
              updated.id = typeof data.message_id === "string" ? data.message_id : updated.id;
              updated.status = "complete";
            }
            if (eventName === "error") updated.status = "failed";
            next[next.length - 1] = updated;
            return next;
          });
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setMessages((current) => current.map((message, index) => index === current.length - 1 && message.role === "assistant" ? { ...message, status: "stopped" } : message));
      } else {
        toast.error(error instanceof Error ? error.message : "Could not generate an answer");
        setMessages((current) => current.map((message, index) => index === current.length - 1 && message.role === "assistant" ? { ...message, status: "failed" } : message));
      }
    } finally {
      abortRef.current = null;
      setSending(false);
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  return <section className="flex h-full min-h-0 flex-col bg-panel">
    <div className="flex h-12 items-center gap-2 border-b px-4"><div className="grid h-7 w-7 place-items-center rounded-lg bg-accent/10 text-accent"><Sparkles size={14}/></div><div className="min-w-0"><p className="text-sm font-medium">Ask DocMind</p><p className="truncate text-[10px] text-ink/45">Grounded in {documentTitle}</p></div></div>
    <div className="min-h-0 flex-1 space-y-5 overflow-auto p-4">
      {loading ? <p className="py-8 text-center text-xs text-ink/40">Loading conversation…</p> : messages.length === 0 ? <div className="py-10 text-center"><Sparkles className="mx-auto text-accent" size={24}/><p className="mt-3 text-sm font-medium">Ask about this document</p><p className="mx-auto mt-1 max-w-xs text-xs leading-5 text-ink/45">Answers are generated from authorized retrieved chunks and retain persisted source citations.</p></div> : messages.map((message, index) => message.role === "user" ? (
        <div key={message.id ?? index} className="ms-auto max-w-[88%] rounded-2xl rounded-ee-md bg-ink px-4 py-3 text-sm leading-6 text-panel">{message.content}</div>
      ) : (
        <article key={message.id ?? index} className="max-w-[94%] text-sm leading-7">
          {message.content ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown> : <div className="h-1.5 w-32 animate-pulse rounded-full bg-muted"/>}
          {message.status && !["complete", "retrieving"].includes(message.status) && <p className="mt-2 text-[10px] uppercase tracking-wide text-ink/35">{message.status}</p>}
          {message.content && <button onClick={()=>navigator.clipboard.writeText(message.content)} className="mt-2 rounded-lg p-1.5 text-ink/45 hover:bg-muted" aria-label="Copy answer"><Copy size={14}/></button>}
          {message.citations.map((citation)=><button key={`${citation.chunk_id}-${citation.ordinal}`} onClick={()=>onCitation?.(citation)} className="mt-3 block w-full rounded-xl border p-3 text-left transition hover:bg-muted/40"><p className="text-[11px] font-semibold uppercase tracking-wide text-ink/45">Source {citation.ordinal}{citation.page_number ? ` · Page ${citation.page_number}` : ""}</p><p className="mt-1 line-clamp-3 text-xs leading-5 text-ink/60">{citation.source_excerpt}</p><span className="mt-2 block text-xs font-medium text-accent">Open source →</span></button>)}
        </article>
      ))}
    </div>
    <div className="border-t p-3"><div className="rounded-2xl border bg-muted/25 p-2 focus-within:ring-2 focus-within:ring-accent/30"><textarea value={query} onChange={(event)=>setQuery(event.target.value)} onKeyDown={(event)=>{if(event.key === "Enter" && !event.shiftKey){event.preventDefault();void send();}}} rows={3} placeholder="Ask about this document…" className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none"/><div className="flex items-center justify-between"><span className="px-2 text-[10px] text-ink/40">Verified sources appear below each answer</span>{sending ? <button onClick={stop} className="grid h-8 w-8 place-items-center rounded-xl bg-ink text-panel" aria-label="Stop generation"><Square size={13}/></button> : <button onClick={()=>void send()} disabled={!query.trim()} className="grid h-8 w-8 place-items-center rounded-xl bg-ink text-panel disabled:opacity-40" aria-label="Send question"><ArrowUp size={15}/></button>}</div></div></div>
  </section>;
}
