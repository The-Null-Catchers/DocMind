"use client";

import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { FileText, Search, ChevronRight } from "lucide-react";
import { PdfViewer } from "@/components/pdf-viewer";
import { ChatPanel } from "@/components/chat-panel";

export default function DocumentWorkspacePage() {
  return <div className="h-full"><PanelGroup direction="horizontal"><Panel defaultSize={18} minSize={13} maxSize={25}><aside className="h-full border-e bg-panel"><div className="border-b p-3"><div className="relative"><Search className="absolute start-2.5 top-2.5 text-ink/35" size={14}/><input className="w-full rounded-xl border bg-muted/30 py-2 pe-2 ps-8 text-xs outline-none focus:ring-2 focus:ring-accent/30" placeholder="Search in document"/></div></div><div className="p-2"><p className="px-2 py-2 text-[10px] font-semibold uppercase tracking-widest text-ink/40">Outline</p>{["Abstract","1. Introduction","2. Retrieval architecture","3. Hybrid ranking","4. Evaluation","5. Conclusions"].map((x,i)=><button key={x} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs text-ink/60 hover:bg-muted"><ChevronRight size={12}/><span className="truncate">{x}</span><span className="ms-auto text-[10px] text-ink/30">{i*6+1}</span></button>)}</div></aside></Panel><PanelResizeHandle className="w-1 bg-transparent hover:bg-accent/30"/><Panel defaultSize={52} minSize={35}><PdfViewer initialPage={31}/></Panel><PanelResizeHandle className="w-1 bg-transparent hover:bg-accent/30"/><Panel defaultSize={30} minSize={22} maxSize={42}><ChatPanel/></Panel></PanelGroup></div>;
}
