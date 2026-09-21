"use client";

import * as Dialog from "@radix-ui/react-dialog";
import {
  FileText,
  MessageSquarePlus,
  NotebookPen,
  Search,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { useUI } from "@/store/ui";

const actions = [
  { icon: Upload, label: "Upload file", href: "/app/documents#upload" },
  { icon: Search, label: "Search workspace", href: "/app/search" },
  { icon: MessageSquarePlus, label: "Open chats", href: "/app/chats" },
  { icon: NotebookPen, label: "Open notes", href: "/app/notes" },
  { icon: Sparkles, label: "Analyze documents", href: "/app/analyze" },
  { icon: FileText, label: "Open document library", href: "/app/documents" },
] as const;

export function CommandPalette() {
  const router = useRouter();
  const { commandOpen, setCommandOpen } = useUI();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const value = query.trim().toLocaleLowerCase();
    if (!value) return actions;
    return actions.filter((action) => action.label.toLocaleLowerCase().includes(value));
  }, [query]);

  function run(href: string) {
    setCommandOpen(false);
    setQuery("");
    router.push(href);
  }

  return (
    <Dialog.Root
      open={commandOpen}
      onOpenChange={(open) => {
        setCommandOpen(open);
        if (!open) setQuery("");
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/35 backdrop-blur-sm" />
        <Dialog.Content
          className="fixed left-1/2 top-[18%] z-50 w-[min(620px,92vw)] -translate-x-1/2 overflow-hidden rounded-2xl border bg-panel shadow-soft"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <div className="flex items-center gap-3 border-b px-4">
            <Search size={18} className="text-ink/45" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && filtered[0]) {
                  event.preventDefault();
                  run(filtered[0].href);
                }
              }}
              className="h-14 flex-1 bg-transparent text-sm outline-none"
              placeholder="Type a command…"
            />
            <Dialog.Close className="rounded p-1 text-ink/45 hover:bg-muted">
              <X size={16} />
            </Dialog.Close>
          </div>
          <div className="p-2">
            {filtered.map(({ icon: Icon, label, href }) => (
              <button
                key={label}
                onClick={() => run(href)}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm hover:bg-muted"
              >
                <Icon size={17} />
                {label}
                <span className="ms-auto text-xs text-ink/35">↵</span>
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="px-3 py-6 text-center text-sm text-ink/45">No matching commands.</p>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
