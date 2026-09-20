"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  Brain,
  Languages,
  Loader2,
  MessageCircleQuestion,
  NotebookPen,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";

type SelectionAction =
  | "explain"
  | "summarize"
  | "rewrite"
  | "translate"
  | "ask"
  | "create_flashcard"
  | "add_to_notes";

type SelectionResult = {
  kind: "generation" | "flashcard" | "note";
  content?: string;
  provider?: string;
  model?: string;
  card_id?: string;
  deck_id?: string;
  note_id?: string;
  citation: {
    document_id: string;
    page_number: number;
    source_excerpt: string;
  };
};

export function SelectionActions({
  workspaceId,
  documentId,
  page,
  selectedText,
  onClear,
}: {
  workspaceId: string;
  documentId: string;
  page: number;
  selectedText: string;
  onClear: () => void;
}) {
  const [busy, setBusy] = useState<SelectionAction | null>(null);
  const [result, setResult] = useState<SelectionResult | null>(null);
  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState("");

  const targetLanguage = useMemo(
    () => /[\u0600-\u06ff]/.test(selectedText) ? "English" : "Arabic",
    [selectedText],
  );

  async function run(action: SelectionAction, extra: Record<string, unknown> = {}) {
    setBusy(action);
    try {
      const response = await api<SelectionResult>("/ai/selection", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: workspaceId,
          document_id: documentId,
          page_number: page,
          selected_text: selectedText,
          action,
          ...extra,
        }),
      });
      if (response.kind === "flashcard") {
        toast.success("Flashcard created from this selection");
        setResult(null);
        onClear();
      } else if (response.kind === "note") {
        toast.success("Selection added to notes");
        setResult(null);
        onClear();
      } else {
        setResult(response);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Selection action failed");
    } finally {
      setBusy(null);
    }
  }

  function submitQuestion(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value) return;
    void run("ask", { question: value });
  }

  return (
    <div className="pointer-events-none absolute inset-x-4 bottom-4 z-30 flex justify-center">
      <div className="pointer-events-auto w-full max-w-3xl overflow-hidden rounded-2xl border bg-panel/95 shadow-xl backdrop-blur">
        <div className="flex items-center gap-1 overflow-x-auto border-b p-2">
          <SelectionButton label="Explain" icon={Sparkles} busy={busy === "explain"} disabled={busy !== null} onClick={() => void run("explain")}/>
          <SelectionButton label="Summarize" icon={Wand2} busy={busy === "summarize"} disabled={busy !== null} onClick={() => void run("summarize")}/>
          <SelectionButton label="Rewrite" icon={Wand2} busy={busy === "rewrite"} disabled={busy !== null} onClick={() => void run("rewrite")}/>
          <SelectionButton label={`Translate to ${targetLanguage}`} icon={Languages} busy={busy === "translate"} disabled={busy !== null} onClick={() => void run("translate", { target_language: targetLanguage })}/>
          <SelectionButton label="Ask" icon={MessageCircleQuestion} busy={busy === "ask"} disabled={busy !== null} onClick={() => setAsking((value) => !value)}/>
          <SelectionButton label="Create flashcard" icon={Brain} busy={busy === "create_flashcard"} disabled={busy !== null} onClick={() => void run("create_flashcard")}/>
          <SelectionButton label="Add to notes" icon={NotebookPen} busy={busy === "add_to_notes"} disabled={busy !== null} onClick={() => void run("add_to_notes")}/>
          <button onClick={onClear} className="focus-ring ms-auto shrink-0 rounded-lg p-2 text-ink/45 hover:bg-muted hover:text-ink" aria-label="Close selection actions"><X size={15}/></button>
        </div>

        <div className="px-3 py-2 text-[11px] text-ink/45">
          Page {page} · “{selectedText.length > 180 ? `${selectedText.slice(0, 180)}…` : selectedText}”
        </div>

        {asking && (
          <form onSubmit={submitQuestion} className="flex gap-2 border-t p-3">
            <input
              autoFocus
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about only this selection…"
              className="min-w-0 flex-1 rounded-xl border bg-muted/25 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30"
              maxLength={2000}
            />
            <button disabled={busy !== null || !question.trim()} className="rounded-xl bg-ink px-4 py-2 text-sm text-panel disabled:opacity-40">Ask</button>
          </form>
        )}

        {result?.kind === "generation" && (
          <div className="max-h-64 overflow-auto border-t p-4">
            <div className="whitespace-pre-wrap text-sm leading-6">{result.content || "No response was generated."}</div>
            <p className="mt-3 text-[11px] text-ink/40">Verified against page {result.citation.page_number} · {result.provider}/{result.model}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function SelectionButton({
  label,
  icon: Icon,
  busy,
  disabled,
  onClick,
}: {
  label: string;
  icon: typeof Sparkles;
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="focus-ring flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs hover:bg-muted disabled:opacity-40"
    >
      {busy ? <Loader2 size={14} className="animate-spin"/> : <Icon size={14}/>}
      {label}
    </button>
  );
}
