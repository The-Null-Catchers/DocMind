"use client";

import { BookOpen, FileText, Home, MessageSquareText, NotebookPen, Brain, GraduationCap, Settings, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useUI } from "@/store/ui";
import { messages } from "@/lib/i18n";

export function Sidebar() {
  const path = usePathname();
  const locale = useUI((s) => s.locale);
  const t = messages[locale];
  const links = [
    ["/app", Home, t.home], ["/app/documents", FileText, t.documents], ["/app/chats", MessageSquareText, t.ai],
    ["/app/notes", NotebookPen, t.notes], ["/app/flashcards", Brain, t.flashcards], ["/app/quizzes", GraduationCap, t.quizzes]
  ] as const;
  return (
    <aside className="flex h-screen w-[244px] shrink-0 flex-col border-e bg-panel p-3">
      <div className="mb-5 flex items-center gap-3 px-2 py-2"><div className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-panel"><BookOpen size={19}/></div><div><div className="font-semibold tracking-tight">DocMind</div><div className="text-[11px] text-ink/50">Knowledge workspace</div></div></div>
      <button className="surface mb-4 flex items-center justify-between px-3 py-2.5 text-left text-sm"><span><span className="block text-[11px] text-ink/45">Workspace</span><span className="font-medium">Research Lab</span></span><span className="text-ink/40">⌄</span></button>
      <nav className="space-y-1">{links.map(([href, Icon, label]) => { const active = href === "/app" ? path === href : path.startsWith(href); return <Link key={href} href={href} className={clsx("focus-ring flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition", active ? "bg-muted font-medium text-ink" : "text-ink/60 hover:bg-muted hover:text-ink")}><Icon size={17}/><span>{label}</span></Link>; })}</nav>
      <div className="mt-auto space-y-1"><div className="mx-2 mb-3 rounded-xl border bg-muted/50 p-3"><div className="mb-1 flex items-center gap-2 text-xs font-semibold"><Sparkles size={14}/> Free plan</div><div className="h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full w-[58%] bg-accent"/></div><p className="mt-2 text-[11px] text-ink/50">290 / 500 pages processed</p></div><Link href="/app/settings" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-ink/60 hover:bg-muted"><Settings size={17}/>Settings</Link></div>
    </aside>
  );
}
