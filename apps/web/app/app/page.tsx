"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Brain,
  CircleAlert,
  CircleCheck,
  Clock3,
  FileText,
  HardDrive,
  Loader2,
  MessageSquare,
  Sparkles,
} from "lucide-react";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type User = { display_name?: string | null; email: string };

type DashboardDocument = {
  id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  status: string;
  processing_progress: number;
  page_count: number | null;
  created_at: string;
  updated_at: string;
};

type DashboardData = {
  documents: {
    total: number;
    ready: number;
    processing: number;
    failed: number;
    storage_bytes: number;
    processed_pages: number;
    ocr_pages: number;
    recent: DashboardDocument[];
    processing_items: DashboardDocument[];
  };
  conversations: Array<{
    id: string;
    title: string;
    pinned: boolean;
    updated_at: string;
  }>;
  study: {
    due_flashcards: number;
    recent_quizzes: Array<{
      id: string;
      title: string;
      difficulty: string;
      language: string;
      updated_at: string;
    }>;
  };
  usage: {
    ai_messages: number;
    metrics: Record<string, number>;
  };
  activity: Array<{
    id: string;
    action: string;
    target_type: string;
    target_id: string | null;
    actor_id: string | null;
    created_at: string;
  }>;
};

export default function DashboardPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const user = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/auth/me") });
  const dashboard = useQuery({
    queryKey: ["dashboard", workspaceId],
    queryFn: () => api<DashboardData>(`/dashboard?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
    refetchInterval: (query) => query.state.data?.documents.processing ? 3000 : false,
  });

  const name = user.data?.display_name?.trim() || user.data?.email?.split("@")[0] || "there";
  const today = new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date());

  return (
    <div className="mx-auto max-w-[1500px] p-6 lg:p-8">
      <div className="mb-7 flex items-end justify-between gap-4">
        <div>
          <p className="text-sm text-ink/50">{today}</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-[-.03em]">Welcome, {name}.</h1>
          <p className="mt-1 text-sm text-ink/55">A live view of your workspace, processing, study queue, and grounded AI activity.</p>
        </div>
        <Link href="/app/documents" className="hidden items-center gap-2 text-sm text-ink/55 hover:text-ink md:flex">
          Open documents <ArrowUpRight size={15}/>
        </Link>
      </div>

      {!workspaceId ? (
        <div className="surface p-8">
          <h2 className="font-semibold">Select a workspace</h2>
          <p className="mt-2 text-sm text-ink/50">Use the workspace selector in the sidebar to start working with documents.</p>
        </div>
      ) : dashboard.isLoading ? (
        <div className="grid min-h-80 place-items-center"><Loader2 className="animate-spin text-ink/35"/></div>
      ) : dashboard.isError || !dashboard.data ? (
        <div className="surface flex items-start gap-3 p-6">
          <CircleAlert size={19} className="mt-0.5 text-red-500"/>
          <div className="min-w-0 flex-1">
            <h2 className="font-medium">Could not load workspace dashboard</h2>
            <p className="mt-1 text-sm text-ink/50">Your documents are unchanged. Retry the live aggregate view.</p>
          </div>
          <button onClick={() => dashboard.refetch()} className="rounded-xl border px-3 py-2 text-sm">Retry</button>
        </div>
      ) : (
        <DashboardContent data={dashboard.data}/>
      )}
    </div>
  );
}

function DashboardContent({ data }: { data: DashboardData }) {
  const documents = data.documents;
  return (
    <>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          icon={FileText}
          label="Documents"
          value={String(documents.total)}
          note={`${documents.ready} ready · ${documents.processing} processing · ${documents.failed} failed`}
        />
        <Metric
          icon={HardDrive}
          label="Workspace storage"
          value={formatBytes(documents.storage_bytes)}
          note={`${documents.processed_pages} pages · ${documents.ocr_pages} OCR pages`}
        />
        <Metric
          icon={Sparkles}
          label="AI messages"
          value={formatCount(data.usage.ai_messages)}
          note="Persisted workspace usage"
        />
        <Metric
          icon={Brain}
          label="Flashcards due"
          value={formatCount(data.study.due_flashcards)}
          note={data.study.recent_quizzes.length ? `${data.study.recent_quizzes.length} recent quizzes` : "No recent quizzes"}
        />
      </section>

      <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,.55fr)]">
        <div className="space-y-6">
          <section>
            <SectionHeading title="Recent documents" href="/app/documents"/>
            <div className="surface overflow-hidden">
              {documents.recent.length === 0 ? (
                <EmptyState icon={FileText} text="No documents yet. Upload your first source to start building this workspace." href="/app/documents#upload"/>
              ) : (
                <>
                  <div className="grid grid-cols-[minmax(0,1fr)_90px_110px_110px] border-b bg-muted/35 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink/40">
                    <span>Name</span><span>Pages</span><span>Status</span><span>Updated</span>
                  </div>
                  {documents.recent.map((document) => (
                    <Link
                      href={`/app/documents/${document.id}`}
                      key={document.id}
                      className="grid grid-cols-[minmax(0,1fr)_90px_110px_110px] items-center border-b px-4 py-3.5 last:border-0 hover:bg-muted/30"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted"><FileText size={17}/></div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{document.title || document.original_filename}</p>
                          <p className="truncate text-xs text-ink/45">{document.mime_type} · {formatBytes(document.file_size)}</p>
                        </div>
                      </div>
                      <span className="text-sm text-ink/55">{document.page_count ?? "—"}</span>
                      <DocumentStatus document={document}/>
                      <span className="text-xs text-ink/45">{formatRelative(document.updated_at)}</span>
                    </Link>
                  ))}
                </>
              )}
            </div>
          </section>

          <section>
            <SectionHeading title="Processing queue"/>
            <div className="surface overflow-hidden">
              {documents.processing_items.length === 0 ? (
                <div className="flex items-center gap-3 p-5 text-sm text-ink/50">
                  <CircleCheck size={17} className="text-emerald-500"/> No documents are processing right now.
                </div>
              ) : documents.processing_items.map((document) => (
                <div key={document.id} className="border-b p-4 last:border-0">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{document.title || document.original_filename}</p>
                      <p className="mt-0.5 text-xs text-ink/45">Processing · {document.processing_progress}%</p>
                    </div>
                    <Link href={`/app/documents/${document.id}`} className="shrink-0 text-xs text-ink/50 hover:text-ink">Open</Link>
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full bg-accent transition-all" style={{ width: `${document.processing_progress}%` }}/>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section>
              <SectionHeading title="Recent conversations" href="/app/chats"/>
              <div className="surface min-h-48 overflow-hidden">
                {data.conversations.length === 0 ? (
                  <EmptyState icon={MessageSquare} text="No conversations yet." href="/app/chats"/>
                ) : data.conversations.map((conversation) => (
                  <Link href="/app/chats" key={conversation.id} className="flex items-center gap-3 border-b p-4 last:border-0 hover:bg-muted/30">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted"><MessageSquare size={16}/></div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{conversation.title}</p>
                      <p className="mt-0.5 text-xs text-ink/40">{formatRelative(conversation.updated_at)}{conversation.pinned ? " · Pinned" : ""}</p>
                    </div>
                    <ArrowUpRight size={14} className="text-ink/30"/>
                  </Link>
                ))}
              </div>
            </section>

            <section>
              <SectionHeading title="Recent quizzes" href="/app/quizzes"/>
              <div className="surface min-h-48 overflow-hidden">
                {data.study.recent_quizzes.length === 0 ? (
                  <EmptyState icon={Brain} text="No quizzes generated yet." href="/app/quizzes"/>
                ) : data.study.recent_quizzes.map((quiz) => (
                  <Link href="/app/quizzes" key={quiz.id} className="flex items-center gap-3 border-b p-4 last:border-0 hover:bg-muted/30">
                    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted"><Brain size={16}/></div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{quiz.title}</p>
                      <p className="mt-0.5 text-xs capitalize text-ink/40">{quiz.difficulty} · {quiz.language.toUpperCase()} · {formatRelative(quiz.updated_at)}</p>
                    </div>
                    <ArrowUpRight size={14} className="text-ink/30"/>
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </div>

        <section>
          <SectionHeading title="Workspace activity"/>
          <div className="surface overflow-hidden">
            {data.activity.length === 0 ? (
              <EmptyState icon={Activity} text="Workspace activity will appear here as you work."/>
            ) : data.activity.map((item) => (
              <div key={item.id} className="flex gap-3 border-b p-4 last:border-0">
                <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-muted"><Activity size={14}/></div>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{formatAction(item.action)}</p>
                  <p className="mt-0.5 truncate text-xs text-ink/40">{item.target_type} · {formatRelative(item.created_at)}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid gap-3">
            <Quick href="/app/chats" icon={Sparkles} title="Ask across your workspace" copy="Start a source-grounded conversation with persisted citations."/>
            <Quick href="/app/flashcards" icon={Brain} title="Review flashcards" copy="Work through due cards and keep your study schedule current."/>
            <Quick href="/app/documents#upload" icon={FileText} title="Add another source" copy="Upload a document and monitor its real processing progress."/>
          </div>
        </section>
      </section>
    </>
  );
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof FileText; label: string; value: string; note: string }) {
  return <div className="surface p-5"><div className="grid h-9 w-9 place-items-center rounded-xl bg-muted"><Icon size={17}/></div><p className="mt-6 text-xs text-ink/45">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p><p className="mt-1 text-xs text-ink/40">{note}</p></div>;
}

function Quick({ href, icon: Icon, title, copy }: { href: string; icon: typeof FileText; title: string; copy: string }) {
  return <Link href={href} className="surface group p-5 text-left transition hover:-translate-y-0.5 hover:shadow-soft"><Icon size={19} className="text-accent"/><h3 className="mt-4 font-medium">{title}</h3><p className="mt-1 text-sm leading-6 text-ink/50">{copy}</p><ArrowUpRight className="mt-4 text-ink/30 transition group-hover:text-ink" size={16}/></Link>;
}

function SectionHeading({ title, href }: { title: string; href?: string }) {
  return <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">{title}</h2>{href && <Link href={href} className="text-sm text-ink/50 hover:text-ink">See all</Link>}</div>;
}

function EmptyState({ icon: Icon, text, href }: { icon: typeof FileText; text: string; href?: string }) {
  const content = <div className="p-8 text-center"><Icon className="mx-auto text-ink/25" size={28}/><p className="mt-3 text-sm text-ink/45">{text}</p></div>;
  return href ? <Link href={href} className="block hover:bg-muted/20">{content}</Link> : content;
}

function DocumentStatus({ document }: { document: DashboardDocument }) {
  if (document.status === "ready") return <span className="flex items-center gap-1.5 text-xs text-ink/60"><CircleCheck size={14} className="text-emerald-500"/>Ready</span>;
  if (document.status === "failed") return <span className="flex items-center gap-1.5 text-xs text-red-600"><CircleAlert size={14}/>Failed</span>;
  return <span className="flex items-center gap-1.5 text-xs text-ink/60"><Clock3 size={14} className="text-amber-500"/>{document.processing_progress}%</span>;
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatCount(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value || 0);
}

function formatRelative(value: string) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "recently";
  const seconds = Math.round((timestamp - Date.now()) / 1000);
  const absolute = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (absolute < 60) return formatter.format(seconds, "second");
  if (absolute < 3600) return formatter.format(Math.round(seconds / 60), "minute");
  if (absolute < 86400) return formatter.format(Math.round(seconds / 3600), "hour");
  if (absolute < 604800) return formatter.format(Math.round(seconds / 86400), "day");
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(timestamp));
}

function formatAction(action: string) {
  return action
    .replaceAll(".", " ")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
