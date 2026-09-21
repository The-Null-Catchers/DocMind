"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, RefreshCw, Settings2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";

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
type Preferences = {
  in_app: boolean;
  email: boolean;
  web_push: boolean;
  mobile_push: boolean;
  document_processing: boolean;
  workspace_invitations: boolean;
  exports: boolean;
  flashcards_due: boolean;
  usage_limits: boolean;
};

const preferenceLabels: Array<[keyof Preferences, string]> = [
  ["in_app", "In-app notifications"],
  ["email", "Email notifications"],
  ["web_push", "Web push"],
  ["mobile_push", "Mobile push"],
  ["document_processing", "Document processing"],
  ["workspace_invitations", "Workspace invitations"],
  ["exports", "Exports"],
  ["flashcards_due", "Flashcards due"],
  ["usage_limits", "Usage warnings"],
];

export default function NotificationsPage() {
  const queryClient = useQueryClient();

  const feed = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<NotificationFeed>("/notifications?limit=100"),
    refetchInterval: 30_000,
  });
  const preferences = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => api<Preferences>("/notifications/preferences"),
  });

  const markRead = useMutation({
    mutationFn: (id: string) => api(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not mark notification read"),
  });

  const markAll = useMutation({
    mutationFn: () => api<void>("/notifications/read-all", { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not mark notifications read"),
  });

  const updatePreferences = useMutation({
    mutationFn: (next: Preferences) =>
      api<Preferences>("/notifications/preferences", {
        method: "PATCH",
        body: JSON.stringify(next),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notification-preferences"] });
      toast.success("Notification preferences saved");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not save preferences"),
  });

  function togglePreference(key: keyof Preferences) {
    if (!preferences.data || updatePreferences.isPending) return;
    updatePreferences.mutate({ ...preferences.data, [key]: !preferences.data[key] });
  }

  return (
    <div className="mx-auto max-w-6xl p-6 lg:p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Notifications</h1>
          <p className="mt-1 text-sm text-ink/50">Processing, collaboration, exports, study reminders, and usage alerts.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => feed.refetch()} className="rounded-xl border p-2.5" aria-label="Refresh notifications"><RefreshCw size={16}/></button>
          {(feed.data?.unread ?? 0) > 0 && (
            <button onClick={() => markAll.mutate()} disabled={markAll.isPending} className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm hover:bg-muted disabled:opacity-40"><CheckCheck size={15}/>Mark all read</button>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <section>
          {feed.isLoading ? (
            <div className="surface p-8 text-sm text-ink/45">Loading notifications…</div>
          ) : feed.isError ? (
            <div className="surface p-8 text-sm text-red-600">Could not load notifications.</div>
          ) : feed.data?.items.length ? (
            <div className="overflow-hidden rounded-2xl border bg-panel">
              <div className="divide-y">
                {feed.data.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => !item.read && markRead.mutate(item.id)}
                    className={`flex w-full items-start gap-3 p-4 text-left hover:bg-muted/40 ${item.read ? "" : "bg-accent/5"}`}
                  >
                    <div className={`mt-0.5 rounded-lg p-2 ${item.read ? "bg-muted text-ink/40" : "bg-accent/10 text-accent"}`}><Bell size={15}/></div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.title}</p>
                        {!item.read && <span className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-medium text-white">Unread</span>}
                        <span className="text-[11px] uppercase tracking-wide text-ink/35">{item.kind.replaceAll("_", " ")}</span>
                      </div>
                      <p className="mt-1 text-sm leading-6 text-ink/60">{item.body}</p>
                      <p className="mt-2 text-[11px] text-ink/35">{new Date(item.created_at).toLocaleString()}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="surface p-10 text-center"><Bell className="mx-auto text-ink/25"/><p className="mt-3 font-medium">No notifications yet</p><p className="mt-1 text-sm text-ink/45">Important workspace events will appear here.</p></div>
          )}
        </section>

        <aside className="surface h-fit p-5">
          <div className="flex items-center gap-2"><Settings2 size={17}/><h2 className="font-medium">Preferences</h2></div>
          <p className="mt-1 text-xs leading-5 text-ink/45">External delivery channels remain optional; local development only needs in-app notifications.</p>
          <div className="mt-4 divide-y">
            {preferenceLabels.map(([key, label]) => (
              <label key={key} className="flex items-center justify-between gap-3 py-3 text-sm">
                <span>{label}</span>
                <input
                  type="checkbox"
                  checked={Boolean(preferences.data?.[key])}
                  disabled={!preferences.data || updatePreferences.isPending}
                  onChange={() => togglePreference(key)}
                />
              </label>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
