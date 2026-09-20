"use client";

import { Bell, Languages, Moon, Search, Sun, Upload } from "lucide-react";
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useUI } from "@/store/ui";
import { messages } from "@/lib/i18n";

type Notification = {
  id: string;
  kind: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  read: boolean;
  created_at: string;
};
type NotificationFeed = { items: Notification[]; unread: number };

export function Topbar() {
  const { theme, setTheme } = useTheme();
  const { locale, setLocale, setCommandOpen } = useUI();
  const queryClient = useQueryClient();
  const router = useRouter();
  const t = messages[locale];

  const notifications = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<NotificationFeed>("/notifications?limit=20"),
    refetchInterval: 30_000,
  });
  const markRead = useMutation({
    mutationFn: (id: string) => api(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const markAllRead = useMutation({
    mutationFn: () => api<void>("/notifications/read-all", { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setCommandOpen]);

  useEffect(() => {
    document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = locale;
  }, [locale]);

  function openNotification(item: Notification) {
    if (!item.read) markRead.mutate(item.id);
    const documentId = typeof item.data.document_id === "string" ? item.data.document_id : null;
    const workspaceId = typeof item.data.workspace_id === "string" ? item.data.workspace_id : null;
    if (documentId) router.push(`/app/documents/${documentId}`);
    else if (workspaceId && item.kind === "workspace_invitation") router.push("/app/settings");
  }

  return (
    <header className="flex h-16 items-center gap-3 border-b bg-panel/85 px-5 backdrop-blur">
      <button onClick={() => setCommandOpen(true)} className="focus-ring flex min-w-0 max-w-xl flex-1 items-center gap-3 rounded-xl border bg-muted/40 px-3 py-2 text-sm text-ink/50">
        <Search size={16}/><span className="truncate">{t.search}</span><span className="ms-auto hidden rounded border bg-panel px-1.5 py-0.5 text-[10px] sm:inline">⌘K</span>
      </button>
      <Button onClick={() => router.push("/app/documents#upload")} className="bg-ink text-panel hover:bg-ink/90"><Upload size={16}/><span className="hidden sm:inline">{t.upload}</span></Button>

      <details className="relative">
        <summary className="focus-ring relative grid h-9 w-9 cursor-pointer list-none place-items-center rounded-xl hover:bg-muted" aria-label="Notifications">
          <Bell size={17}/>
          {(notifications.data?.unread ?? 0) > 0 && <span className="absolute -end-1 -top-1 min-w-4 rounded-full bg-red-600 px-1 text-center text-[10px] leading-4 text-white">{Math.min(99, notifications.data?.unread ?? 0)}</span>}
        </summary>
        <div className="absolute end-0 z-50 mt-2 w-[min(380px,90vw)] overflow-hidden rounded-2xl border bg-panel shadow-soft">
          <div className="flex items-center justify-between border-b px-4 py-3"><p className="text-sm font-semibold">Notifications</p>{(notifications.data?.unread ?? 0) > 0 && <button onClick={() => markAllRead.mutate()} className="text-xs text-accent">Mark all read</button>}</div>
          <div className="max-h-[420px] overflow-auto">
            {notifications.isLoading && <p className="p-4 text-sm text-ink/45">Loading…</p>}
            {notifications.data?.items.map((item) => <button key={item.id} onClick={() => openNotification(item)} className={`block w-full border-b px-4 py-3 text-left last:border-0 hover:bg-muted/50 ${item.read ? "" : "bg-accent/5"}`}>
              <div className="flex items-start gap-2"><span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.read ? "bg-transparent" : "bg-accent"}`}/><span className="min-w-0"><span className="block text-sm font-medium">{item.title}</span><span className="mt-1 block text-xs leading-5 text-ink/55">{item.body}</span><span className="mt-1 block text-[10px] text-ink/35">{new Date(item.created_at).toLocaleString()}</span></span></div>
            </button>)}
            {!notifications.isLoading && notifications.data?.items.length === 0 && <p className="p-6 text-center text-sm text-ink/45">No notifications yet.</p>}
          </div>
        </div>
      </details>

      <Button aria-label="Switch language" onClick={() => setLocale(locale === "en" ? "ar" : "en")}><Languages size={17}/><span className="text-xs">{locale.toUpperCase()}</span></Button>
      <Button aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun size={17}/> : <Moon size={17}/>}</Button>
    </header>
  );
}
