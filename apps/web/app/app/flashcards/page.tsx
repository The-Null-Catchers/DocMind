"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type Card = {
  id: string;
  deck_id: string;
  front: string;
  back: string;
  due_at: string | null;
  sources: Array<{ document_id?: string; page_number?: number }>;
};

export default function FlashcardsPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const queryClient = useQueryClient();
  const [revealed, setRevealed] = useState(false);
  const [index, setIndex] = useState(0);

  const cards = useQuery({
    queryKey: ["flashcards-due", workspaceId],
    queryFn: () => api<Card[]>(`/flashcards/due?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const current = useMemo(() => cards.data?.[index] ?? null, [cards.data, index]);
  const review = useMutation({
    mutationFn: ({ id, rating }: { id: string; rating: string }) =>
      api(`/flashcards/${id}/review`, { method: "POST", body: JSON.stringify({ rating }) }),
    onSuccess: async () => {
      setRevealed(false);
      setIndex(0);
      await queryClient.invalidateQueries({ queryKey: ["flashcards-due", workspaceId] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not save review"),
  });

  if (!workspaceId) return <div className="p-8 text-sm text-ink/50">Select a workspace to review flashcards.</div>;

  return (
    <div className="mx-auto max-w-4xl p-6 lg:p-8">
      <div className="flex items-end justify-between">
        <div><h1 className="text-2xl font-semibold">Flashcards</h1><p className="mt-1 text-sm text-ink/50">Review due cards with persisted SM-2 scheduling.</p></div>
        <button onClick={() => cards.refetch()} className="rounded-xl border p-2.5" aria-label="Refresh due cards"><RotateCcw size={16}/></button>
      </div>

      {cards.isLoading ? <div className="surface mt-6 p-8 text-sm text-ink/45">Loading due cards…</div> :
       cards.isError ? <div className="surface mt-6 p-8 text-sm text-red-600">Could not load due cards.</div> :
       !current ? <div className="surface mt-6 p-8 text-center"><p className="font-medium">You are caught up.</p><p className="mt-1 text-sm text-ink/45">No cards are due right now.</p></div> :
       <section className="surface mt-6 overflow-hidden">
         <div className="border-b px-5 py-3 text-xs text-ink/45">{cards.data?.length ?? 0} due · card {index + 1}</div>
         <button onClick={() => setRevealed((value) => !value)} className="block min-h-[320px] w-full p-8 text-left">
           <p className="text-xs font-semibold uppercase tracking-wider text-ink/35">{revealed ? "Answer" : "Question"}</p>
           <div className="mt-8 text-xl leading-9">{revealed ? current.back : current.front}</div>
           <p className="mt-8 text-xs text-ink/40">{revealed ? "Rate your recall below." : "Tap the card to reveal the answer."}</p>
         </button>
         {revealed && <div className="grid grid-cols-4 gap-2 border-t p-4">
           {["again","hard","good","easy"].map((rating) => (
             <button key={rating} disabled={review.isPending} onClick={() => review.mutate({ id: current.id, rating })} className="rounded-xl border px-3 py-2 text-sm capitalize hover:bg-muted disabled:opacity-50">{rating}</button>
           ))}
         </div>}
       </section>}
    </div>
  );
}
