"use client";

import { Download } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { createExport, type ExportKind } from "@/lib/exports";

export type ExportOption = {
  kind: ExportKind;
  label: string;
  payload?: Record<string, unknown>;
};

export function ExportActions({
  workspaceId,
  sourceId,
  options,
  compact = false,
}: {
  workspaceId: string;
  sourceId?: string | null;
  options: ExportOption[];
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
  const exportMutation = useMutation({
    mutationFn: (option: ExportOption) =>
      createExport({
        workspaceId,
        sourceId,
        kind: option.kind,
        payload: option.payload,
      }),
    onSuccess: async (job) => {
      await queryClient.invalidateQueries({ queryKey: ["exports", workspaceId] });
      toast.success(
        job.status === "ready"
          ? "Export is ready. Open Settings → Exports to download it."
          : "Export queued. You’ll be notified when it is ready.",
      );
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Could not create export"),
  });

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.kind}
          type="button"
          onClick={() => exportMutation.mutate(option)}
          disabled={exportMutation.isPending}
          className={
            compact
              ? "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-40"
              : "flex items-center gap-2 rounded-xl border px-3 py-2 text-sm hover:bg-muted disabled:opacity-40"
          }
        >
          <Download size={compact ? 13 : 15}/>
          {option.label}
        </button>
      ))}
    </div>
  );
}
