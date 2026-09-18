import { api, apiBlob } from "@/lib/api";

export type ExportKind =
  | "note_markdown"
  | "note_pdf"
  | "chat_markdown"
  | "chat_pdf"
  | "flashcards_csv"
  | "quiz_pdf"
  | "summary_pdf"
  | "extraction_json"
  | "extraction_csv";

export type ExportJob = {
  id: string;
  workspace_id: string;
  kind: ExportKind;
  source_id: string | null;
  status: "pending" | "processing" | "ready" | "failed";
  filename: string | null;
  mime_type: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export async function createExport(input: {
  workspaceId: string;
  kind: ExportKind;
  sourceId?: string | null;
  payload?: Record<string, unknown>;
}): Promise<ExportJob> {
  return api<ExportJob>("/exports", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: input.workspaceId,
      kind: input.kind,
      source_id: input.sourceId ?? null,
      payload: input.payload ?? {},
    }),
  });
}

export async function downloadExport(job: Pick<ExportJob, "id" | "filename">): Promise<void> {
  const blob = await apiBlob(`/exports/${job.id}/file`);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = job.filename || "docmind-export";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
