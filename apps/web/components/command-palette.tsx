"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { FilePlus2, MessageSquarePlus, NotebookPen, Search, Upload, X } from "lucide-react";
import { useUI } from "@/store/ui";

export function CommandPalette() {
  const { commandOpen, setCommandOpen } = useUI();
  const actions = [[Upload,"Upload file"],[Search,"Search workspace"],[MessageSquarePlus,"New chat"],[NotebookPen,"Create note"],[FilePlus2,"Generate quiz"]] as const;
  return <Dialog.Root open={commandOpen} onOpenChange={setCommandOpen}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/35 backdrop-blur-sm"/><Dialog.Content className="fixed left-1/2 top-[18%] z-50 w-[min(620px,92vw)] -translate-x-1/2 overflow-hidden rounded-2xl border bg-panel shadow-soft"><Dialog.Title className="sr-only">Command palette</Dialog.Title><div className="flex items-center gap-3 border-b px-4"><Search size={18} className="text-ink/45"/><input autoFocus className="h-14 flex-1 bg-transparent text-sm outline-none" placeholder="Type a command or search…"/><Dialog.Close className="rounded p-1 text-ink/45 hover:bg-muted"><X size={16}/></Dialog.Close></div><div className="p-2">{actions.map(([Icon,label]) => <button key={label} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm hover:bg-muted"><Icon size={17}/>{label}<span className="ms-auto text-xs text-ink/35">↵</span></button>)}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
