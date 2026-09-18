"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type QuizSummary = { id: string; title: string; language: string; difficulty: string };
type QuizQuestion = {
  id: string;
  question_type: string;
  question: string;
  options: string[];
  sources: Array<{ document_id?: string; page_number?: number }>;
};
type Quiz = QuizSummary & { questions: QuizQuestion[] };
type Result = {
  score: number;
  correct: number;
  total: number;
  results: Array<{ question_id: string; correct: boolean; answer: string; explanation: string; sources: Array<Record<string, unknown>> }>;
};

export default function QuizzesPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result | null>(null);

  const quizzes = useQuery({
    queryKey: ["quizzes", workspaceId],
    queryFn: () => api<QuizSummary[]>(`/quizzes?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const quiz = useQuery({
    queryKey: ["quiz", selectedId],
    queryFn: () => api<Quiz>(`/quizzes/${selectedId}`),
    enabled: Boolean(selectedId),
  });

  const submit = useMutation({
    mutationFn: () => api<Result>(`/quizzes/${selectedId}/attempts`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),
    onSuccess: setResult,
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not submit quiz"),
  });

  if (!workspaceId) return <div className="p-8 text-sm text-ink/50">Select a workspace to open quizzes.</div>;

  return (
    <div className="grid h-full min-h-0 grid-cols-[280px_1fr]">
      <aside className="min-h-0 overflow-auto border-e bg-panel p-3">
        <h1 className="px-2 py-3 text-xl font-semibold">Quizzes</h1>
        {quizzes.isLoading && <p className="px-2 text-sm text-ink/45">Loading quizzes…</p>}
        {quizzes.data?.map((item) => (
          <button
            key={item.id}
            onClick={() => { setSelectedId(item.id); setAnswers({}); setResult(null); }}
            className={`mb-1 w-full rounded-xl px-3 py-2 text-left ${selectedId === item.id ? "bg-muted" : "hover:bg-muted/60"}`}
          >
            <p className="truncate text-sm font-medium">{item.title}</p>
            <p className="mt-1 text-xs capitalize text-ink/45">{item.difficulty} · {item.language.toUpperCase()}</p>
          </button>
        ))}
        {!quizzes.isLoading && quizzes.data?.length === 0 && <p className="px-2 py-8 text-center text-sm text-ink/45">No quizzes yet.</p>}
      </aside>

      <main className="min-h-0 overflow-auto p-6 lg:p-8">
        {!selectedId ? (
          <div className="grid min-h-[60vh] place-items-center text-center"><div><h2 className="text-xl font-semibold">Choose a quiz</h2><p className="mt-2 text-sm text-ink/45">Attempts and scoring are saved to your account.</p></div></div>
        ) : quiz.isLoading ? (
          <p className="text-sm text-ink/45">Loading quiz…</p>
        ) : quiz.data ? (
          <div className="mx-auto max-w-3xl">
            <h2 className="text-2xl font-semibold">{quiz.data.title}</h2>
            <p className="mt-1 text-sm capitalize text-ink/45">{quiz.data.questions.length} questions · {quiz.data.difficulty}</p>

            <div className="mt-6 space-y-4">
              {quiz.data.questions.map((question, index) => {
                const judged = result?.results.find((item) => item.question_id === question.id);
                return (
                  <section key={question.id} className="surface p-5">
                    <p className="text-xs font-semibold uppercase tracking-wider text-ink/35">Question {index + 1}</p>
                    <p className="mt-3 font-medium leading-7">{question.question}</p>
                    {question.options?.length ? (
                      <div className="mt-4 space-y-2">
                        {question.options.map((option) => (
                          <label key={option} className="flex cursor-pointer gap-3 rounded-xl border p-3 text-sm">
                            <input type="radio" name={question.id} value={option} checked={answers[question.id] === option} disabled={Boolean(result)} onChange={() => setAnswers((current) => ({ ...current, [question.id]: option }))}/>
                            <span>{option}</span>
                          </label>
                        ))}
                      </div>
                    ) : (
                      <textarea
                        aria-label={`Answer question ${index + 1}`}
                        value={answers[question.id] ?? ""}
                        disabled={Boolean(result)}
                        onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
                        className="mt-4 min-h-24 w-full rounded-xl border bg-transparent p-3 text-sm outline-none focus:ring-2 focus:ring-accent/30"
                        placeholder="Your answer"
                      />
                    )}
                    {judged && <div className={`mt-4 rounded-xl p-3 text-sm ${judged.correct ? "bg-emerald-500/10 text-emerald-700" : "bg-red-500/10 text-red-700"}`}>
                      <p className="font-medium">{judged.correct ? "Correct" : "Not correct"}</p>
                      {!judged.correct && <p className="mt-1">Expected: {judged.answer}</p>}
                      {judged.explanation && <p className="mt-2 opacity-80">{judged.explanation}</p>}
                    </div>}
                  </section>
                );
              })}
            </div>

            {result ? (
              <div className="surface mt-5 p-5"><p className="text-sm text-ink/45">Completed</p><p className="mt-1 text-3xl font-semibold">{result.score.toFixed(0)}%</p><p className="mt-1 text-sm text-ink/50">{result.correct} of {result.total} correct</p></div>
            ) : (
              <button onClick={() => submit.mutate()} disabled={submit.isPending || Object.keys(answers).length === 0} className="mt-5 rounded-xl bg-ink px-5 py-2.5 text-sm font-medium text-panel disabled:opacity-40">Submit quiz</button>
            )}
          </div>
        ) : <p className="text-sm text-red-600">Could not load quiz.</p>}
      </main>
    </div>
  );
}
