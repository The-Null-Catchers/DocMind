"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Brain, CircleAlert, CircleCheck, Clock3, FileText, Loader2, Sparkles } from "lucide-react";

import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type User = { display_name?: string | null; email: string };
type DocumentRow = { id: string; title: string; original_filename: string; status: string; processing_progress: number; page_count: number | null; mime_type: string };
type Flashcard = { id: string };
type Usage = { plan: string; usage: Record<string, number>; limits: Record<string, number> };

export default function DashboardPage() {
  const workspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const user = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/auth/me") });
  const documents = useQuery({
    queryKey: ["documents", workspaceId],
    queryFn: () => api<DocumentRow[]>(`/documents?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
    refetchInterval: (query) => query.state.data?.some((doc) => !["ready", "failed"].includes(doc.status)) ? 3000 : false,
  });
  const dueCards = useQuery({
    queryKey: ["flashcards", "due", workspaceId],
    queryFn: () => api<Flashcard[]>(`/flashcards/due?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });
  const usage = useQuery({
    queryKey: ["usage", workspaceId],
    queryFn: () => api<Usage>(`/usage?workspace_id=${encodeURIComponent(workspaceId!)}`),
    enabled: Boolean(workspaceId),
  });

  const name = user.data?.display_name?.trim() || user.data?.email?.split("@")[0] || "there";
  const recent = (documents.data ?? []).slice(0, 6);
  const ready = (documents.data ?? []).filter((doc) => doc.status === "ready").length;
  const pages = Number(usage.data?.usage.pages_processed ?? 0);
  const pageLimit = Number(usage.data?.limits.pages_processed ?? usage.data?.limits.pages ?? 0);
  const today = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date());

  return <div className="mx-auto max-w-[1500px] p-6 lg:p-8">
    <div className="mb-7 flex items-end justify-between"><div><p className="text-sm text-ink/50">{today}</p><h1 className="mt-1 text-3xl font-semibold tracking-[-.03em]">Welcome, {name}.</h1><p className="mt-1 text-sm text-ink/55">Search, study, and ask questions grounded in your own sources.</p></div><Link href="/app/documents" className="hidden items-center gap-2 text-sm text-ink/55 hover:text-ink md:flex">Open documents <ArrowUpRight size={15}/></Link></div>

    {!workspaceId ? <div className="surface p-8"><h2 className="font-semibold">Select a workspace</h2><p className="mt-2 text-sm text-ink/50">Use the workspace selector in the sidebar to start working with documents.</p></div> : (
      <>
        <section className="grid gap-4 lg:grid-cols-3">
          <Metric icon={FileText} label="Documents" value={`${documents.data?.length ?? 0}`} note={`${ready} ready`}/>
          <Metric icon={Brain} label="Due now" value={`${dueCards.data?.length ?? 0} cards`} note="spaced repetition"/>
          <Metric icon={Sparkles} label="Pages processed" value={`${pages}`} note={pageLimit > 0 ? `of ${pageLimit} on ${usage.data?.plan ?? "free"}` : `${usage.data?.plan ?? "free"} plan`}/>
        </section>

        <section className="mt-8"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Recent documents</h2><Link href="/app/documents" className="text-sm text-ink/50 hover:text-ink">See all</Link></div>
          <div className="surface overflow-hidden">
            {documents.isLoading ? <div className="grid place-items-center p-12"><Loader2 className="animate-spin text-ink/35"/></div> : documents.isError ? <div className="flex items-center gap-2 p-6 text-sm text-red-600"><CircleAlert size={17}/>Could not load documents.</div> : recent.length === 0 ? <div className="p-8 text-center text-sm text-ink/45">No documents yet. <Link href="/app/documents" className="font-medium text-ink underline">Upload your first source.</Link></div> : <>
              <div className="grid grid-cols-[1fr_130px_120px] border-b bg-muted/35 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink/40"><span>Name</span><span>Pages</span><span>Status</span></div>
              {recent.map((doc)=><Link href={`/app/documents/${doc.id}`} key={doc.id} className="grid grid-cols-[1fr_130px_120px] items-center border-b px-4 py-3.5 last:border-0 hover:bg-muted/30"><div className="flex min-w-0 items-center gap-3"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted"><FileText size={17}/></div><div className="min-w-0"><p className="truncate text-sm font-medium">{doc.title || doc.original_filename}</p><p className="truncate text-xs text-ink/45">{doc.mime_type}</p></div></div><span className="text-sm text-ink/55">{doc.page_count ?? "—"}</span><span className="flex items-center gap-1.5 text-xs text-ink/60">{doc.status === "ready" ? <CircleCheck size={14} className="text-emerald-500"/> : doc.status === "failed" ? <CircleAlert size={14} className="text-red-500"/> : <Clock3 size={14} className="text-amber-500"/>}{doc.status === "ready" ? "Ready" : doc.status === "failed" ? "Failed" : `${doc.processing_progress ?? 0}%`}</span></Link>)}
            </>}
          </div>
        </section>

        <section className="mt-8 grid gap-4 md:grid-cols-3">
          <Quick href="/app/chats" icon={Sparkles} title="Ask across your workspace" copy="Start a source-grounded conversation with persisted citations."/>
          <Quick href="/app/flashcards" icon={Brain} title="Review flashcards" copy="Work through cards that are due now and keep your study schedule current."/>
          <Quick href="/app/documents" icon={FileText} title="Add another source" copy="Upload a document and watch its processing state from ingestion to ready."/>
        </section>
      </>
    )}
  </div>;
}

function Metric({icon:Icon,label,value,note}:{icon:typeof FileText,label:string,value:string,note:string}){return <div className="surface p-5"><div className="grid h-9 w-9 place-items-center rounded-xl bg-muted"><Icon size={17}/></div><p className="mt-7 text-xs text-ink/45">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p><p className="text-xs text-ink/40">{note}</p></div>}
function Quick({href,icon:Icon,title,copy}:{href:string,icon:typeof FileText,title:string,copy:string}){return <Link href={href} className="surface group p-5 text-left transition hover:-translate-y-0.5 hover:shadow-soft"><Icon size={19} className="text-accent"/><h3 className="mt-5 font-medium">{title}</h3><p className="mt-1 text-sm leading-6 text-ink/50">{copy}</p><ArrowUpRight className="mt-4 text-ink/30 transition group-hover:text-ink" size={16}/></Link>}
