"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, FileText, Home, MessageSquareText, NotebookPen, Brain, GraduationCap, Settings, Sparkles, FolderOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { api } from "@/lib/api";
import { useUI } from "@/store/ui";
import { useWorkspaceStore } from "@/store/workspace";
import { messages } from "@/lib/i18n";

type Workspace = { id: string; name: string; role: string };
type Usage = { plan: string; usage: Record<string, number>; limits: Record<string, number> };

export function Sidebar() {
  const path = usePathname();
  const locale = useUI((s) => s.locale);
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const setActiveWorkspaceId = useWorkspaceStore((s) => s.setActiveWorkspaceId);
  const t = messages[locale];
  const workspaces = useQuery({ queryKey: ["workspaces"], queryFn: () => api<Workspace[]>("/workspaces") });

  useEffect(() => {
    if (!workspaces.data?.length) return;
    if (!activeWorkspaceId || !workspaces.data.some((workspace) => workspace.id === activeWorkspaceId)) {
      setActiveWorkspaceId(workspaces.data[0].id);
    }
  }, [activeWorkspaceId, setActiveWorkspaceId, workspaces.data]);

  const usage = useQuery({
    queryKey: ["usage", activeWorkspaceId],
    queryFn: () => api<Usage>(`/usage?workspace_id=${encodeURIComponent(activeWorkspaceId!)}`),
    enabled: Boolean(activeWorkspaceId),
  });
  const selected = workspaces.data?.find((workspace) => workspace.id === activeWorkspaceId);
  const pages = Number(usage.data?.usage.pages_processed ?? 0);
  const pageLimit = Number(usage.data?.limits.pages_processed ?? usage.data?.limits.pages ?? 0);
  const pct = pageLimit > 0 ? Math.min(100, (pages / pageLimit) * 100) : 0;

  const links = [
    ["/app", Home, t.home],
    ["/app/documents", FileText, t.documents],
    ["/app/chats", MessageSquareText, t.ai],
    ["/app/notes", NotebookPen, t.notes],
    ["/app/flashcards", Brain, t.flashcards],
    ["/app/quizzes", GraduationCap, t.quizzes],
  ] as const;

  return (
    <aside className="flex h-screen w-[244px] shrink-0 flex-col border-e bg-panel p-3">
      <div className="mb-5 flex items-center gap-3 px-2 py-2"><div className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-panel"><BookOpen size={19}/></div><div><div className="font-semibold tracking-tight">DocMind</div><div className="text-[11px] text-ink/50">Knowledge workspace</div></div></div>
      <label className="surface mb-4 block px-3 py-2 text-left text-sm">
        <span className="block text-[11px] text-ink/45">Workspace</span>
        {workspaces.isLoading ? <span className="mt-1 block text-ink/45">Loading…</span> : workspaces.data?.length ? (
          <select aria-label="Active workspace" value={activeWorkspaceId ?? ""} onChange={(event)=>setActiveWorkspaceId(event.target.value)} className="mt-1 w-full bg-transparent font-medium outline-none">
            {workspaces.data.map((workspace)=><option key={workspace.id} value={workspace.id}>{workspace.name} · {workspace.role}</option>)}
          </select>
        ) : <span className="mt-1 flex items-center gap-2 text-ink/45"><FolderOpen size={14}/>No workspace</span>}
      </label>
      <nav className="space-y-1">{links.map(([href, Icon, label]) => { const active = href === "/app" ? path === href : path.startsWith(href); return <Link key={href} href={href} className={clsx("focus-ring flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition", active ? "bg-muted font-medium text-ink" : "text-ink/60 hover:bg-muted hover:text-ink")}><Icon size={17}/><span>{label}</span></Link>; })}</nav>
      <div className="mt-auto space-y-1">
        {activeWorkspaceId && <div className="mx-2 mb-3 rounded-xl border bg-muted/50 p-3"><div className="mb-1 flex items-center gap-2 text-xs font-semibold"><Sparkles size={14}/> {(usage.data?.plan ?? "free").toUpperCase()} plan</div><div className="h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full bg-accent" style={{width:`${pct}%`}}/></div><p className="mt-2 text-[11px] text-ink/50">{pageLimit > 0 ? `${pages} / ${pageLimit} pages processed` : `${pages} pages processed`}</p><p className="mt-1 truncate text-[11px] text-ink/35">{selected?.name}</p></div>}
        <Link href="/app/settings" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-ink/60 hover:bg-muted"><Settings size={17}/>Settings</Link>
      </div>
    </aside>
  );
}
