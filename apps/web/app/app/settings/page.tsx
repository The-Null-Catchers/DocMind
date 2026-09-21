"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailPlus, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, logoutLocal } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type User = {
  id: string;
  email: string;
  display_name: string;
  locale: string;
  is_email_verified: boolean;
};
type Session = {
  id: string;
  device_name: string | null;
  created_at: string;
  expires_at: string;
  revoked: boolean;
};
type Member = {
  user_id: string;
  email: string;
  display_name: string;
  role: "owner" | "admin" | "editor" | "viewer";
  created_at: string;
};
type Invitation = {
  id: string;
  workspace_id?: string;
  workspace_name?: string | null;
  email: string;
  role: "admin" | "editor" | "viewer";
  status: string;
  expires_at: string;
  last_sent_at: string;
  dev_token?: string;
};

export default function SettingsPage() {
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const queryClient = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "editor" | "viewer">("viewer");

  const me = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/auth/me") });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api<Session[]>("/auth/sessions") });
  const members = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => api<Member[]>(`/workspaces/${workspaceId}/members`),
    enabled: Boolean(workspaceId),
  });
  const invitationInbox = useQuery({
    queryKey: ["invitation-inbox"],
    queryFn: () => api<Invitation[]>("/workspace-invitations"),
  });

  const invitations = useQuery({
    queryKey: ["workspace-invitations", workspaceId],
    queryFn: () => api<Invitation[]>(`/workspaces/${workspaceId}/invitations`),
    enabled: Boolean(workspaceId),
    retry: false,
  });

  const acceptInvitation = useMutation({
    mutationFn: (id: string) => api(`/workspace-invitations/${id}/accept`, { method: "POST" }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["invitation-inbox"] }),
        queryClient.invalidateQueries({ queryKey: ["workspaces"] }),
      ]);
      toast.success("Workspace invitation accepted");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not accept invitation"),
  });

  const rejectInvitation = useMutation({
    mutationFn: (id: string) => api<void>(`/workspace-invitations/${id}/reject`, { method: "POST" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["invitation-inbox"] });
      toast.success("Workspace invitation declined");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not decline invitation"),
  });

  const currentMember = members.data?.find((member) => member.user_id === me.data?.id);
  const canManage = currentMember?.role === "owner" || currentMember?.role === "admin";
  const isOwner = currentMember?.role === "owner";

  const invite = useMutation({
    mutationFn: () => api<Invitation>(`/workspaces/${workspaceId}/invitations`, {
      method: "POST",
      body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
    }),
    onSuccess: async (result) => {
      setInviteEmail("");
      await queryClient.invalidateQueries({ queryKey: ["workspace-invitations", workspaceId] });
      toast.success(result.dev_token ? `Invitation created. Development token: ${result.dev_token}` : "Invitation created.");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not create invitation"),
  });

  const updateRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api(`/workspaces/${workspaceId}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not change member role"),
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) => api<void>(`/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not remove member"),
  });

  const resendInvite = useMutation({
    mutationFn: (id: string) => api<Invitation>(`/workspaces/${workspaceId}/invitations/${id}/resend`, { method: "POST" }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["workspace-invitations", workspaceId] });
      toast.success(result.dev_token ? `Invitation resent. Development token: ${result.dev_token}` : "Invitation resent.");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not resend invitation"),
  });

  const revokeInvite = useMutation({
    mutationFn: (id: string) => api<void>(`/workspaces/${workspaceId}/invitations/${id}`, { method: "DELETE" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["workspace-invitations", workspaceId] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not revoke invitation"),
  });

  const verifyEmail = useMutation({
    mutationFn: () => api<{ message: string; dev_token?: string }>("/auth/email-verification/request", { method: "POST" }),
    onSuccess: (result) => toast.success(result.dev_token ? `Verification token: ${result.dev_token}` : result.message),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not request verification"),
  });

  const revokeSession = useMutation({
    mutationFn: (id: string) => api<void>(`/auth/sessions/${id}`, { method: "DELETE" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not revoke session"),
  });

  const deleteAccount = useMutation({
    mutationFn: () => api<void>("/auth/account", { method: "DELETE" }),
    onSuccess: () => {
      logoutLocal();
      window.location.assign("/login");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not delete account"),
  });

  return (
    <div className="mx-auto max-w-6xl p-6 lg:p-8">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <p className="mt-1 text-sm text-ink/50">Account security and workspace collaboration are enforced by the server.</p>

      <section className="surface mt-6 p-5">
        <div className="flex items-start justify-between gap-4">
          <div><h2 className="font-medium">Account</h2><p className="mt-1 text-sm text-ink/50">{me.data?.email ?? "Loading profile…"}</p></div>
          {me.data && <span className={`rounded-full px-2 py-1 text-xs ${me.data.is_email_verified ? "bg-emerald-500/10 text-emerald-700" : "bg-amber-500/10 text-amber-700"}`}>{me.data.is_email_verified ? "Verified" : "Unverified"}</span>}
        </div>
        {me.data && !me.data.is_email_verified && <button onClick={() => verifyEmail.mutate()} disabled={verifyEmail.isPending} className="mt-4 flex items-center gap-2 rounded-xl border px-3 py-2 text-sm hover:bg-muted"><ShieldCheck size={15}/>Request verification</button>}

        <div className="mt-6 border-t pt-5">
          <h3 className="text-sm font-medium">Sessions & devices</h3>
          <div className="mt-3 divide-y rounded-xl border">
            {sessions.data?.map((session) => <div key={session.id} className="flex items-center gap-3 p-3">
              <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{session.device_name || "Unknown device"}</p><p className="text-xs text-ink/40">{session.revoked ? "Revoked" : `Expires ${new Date(session.expires_at).toLocaleString()}`}</p></div>
              {!session.revoked && <button onClick={() => revokeSession.mutate(session.id)} className="rounded-lg border px-3 py-1.5 text-xs hover:bg-muted">Revoke</button>}
            </div>)}
            {!sessions.isLoading && sessions.data?.length === 0 && <p className="p-3 text-sm text-ink/45">No sessions found.</p>}
          </div>
        </div>
      </section>

      <section className="surface mt-6 p-5">
        <h2 className="font-medium">Invitations for you</h2>
        <p className="mt-1 text-sm text-ink/50">Accept or decline workspace invitations sent to your account email.</p>
        <div className="mt-4 divide-y rounded-xl border">
          {invitationInbox.isLoading && <p className="p-4 text-sm text-ink/45">Loading invitations…</p>}
          {invitationInbox.data?.map((invitation) => <div key={invitation.id} className="flex flex-wrap items-center gap-3 p-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{invitation.workspace_name || "Shared workspace"}</p>
              <p className="text-xs capitalize text-ink/40">{invitation.role} · expires {new Date(invitation.expires_at).toLocaleString()}</p>
            </div>
            <button onClick={() => rejectInvitation.mutate(invitation.id)} disabled={rejectInvitation.isPending || acceptInvitation.isPending} className="rounded-lg border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-40">Decline</button>
            <button onClick={() => acceptInvitation.mutate(invitation.id)} disabled={rejectInvitation.isPending || acceptInvitation.isPending} className="rounded-lg bg-ink px-3 py-1.5 text-xs text-panel disabled:opacity-40">Accept</button>
          </div>)}
          {!invitationInbox.isLoading && invitationInbox.data?.length === 0 && <p className="p-4 text-sm text-ink/45">No pending invitations.</p>}
        </div>
      </section>

      {workspaceId && <section className="surface mt-6 p-5">
        <h2 className="font-medium">Workspace members</h2>
        <p className="mt-1 text-sm text-ink/50">Your effective role is {currentMember?.role ?? "loading"}.</p>
        <div className="mt-4 divide-y rounded-xl border">
          {members.data?.map((member) => {
            const protectedMember = member.role === "owner" || (!isOwner && member.role === "admin");
            return <div key={member.user_id} className="flex flex-wrap items-center gap-3 p-3">
              <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{member.display_name || member.email}</p><p className="truncate text-xs text-ink/40">{member.email}</p></div>
              {canManage && !protectedMember ? <select value={member.role} onChange={(event) => updateRole.mutate({ userId: member.user_id, role: event.target.value })} className="rounded-lg border bg-panel px-2 py-1.5 text-xs">
                <option value="viewer">Viewer</option><option value="editor">Editor</option>{isOwner && <option value="admin">Admin</option>}
              </select> : <span className="rounded-full bg-muted px-2 py-1 text-xs capitalize">{member.role}</span>}
              {canManage && !protectedMember && member.user_id !== me.data?.id && <button onClick={() => removeMember.mutate(member.user_id)} className="rounded-lg p-2 text-red-600 hover:bg-red-50" aria-label="Remove member"><Trash2 size={15}/></button>}
            </div>;
          })}
        </div>

        {canManage && <div className="mt-6 border-t pt-5">
          <h3 className="text-sm font-medium">Invite member</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            <input value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} type="email" placeholder="person@example.com" className="min-w-64 flex-1 rounded-xl border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30"/>
            <select value={inviteRole} onChange={(event) => setInviteRole(event.target.value as typeof inviteRole)} className="rounded-xl border bg-panel px-3 py-2 text-sm"><option value="viewer">Viewer</option><option value="editor">Editor</option>{isOwner && <option value="admin">Admin</option>}</select>
            <button onClick={() => invite.mutate()} disabled={!inviteEmail.trim() || invite.isPending} className="flex items-center gap-2 rounded-xl bg-ink px-4 py-2 text-sm text-panel disabled:opacity-40"><MailPlus size={15}/>Invite</button>
          </div>
          {!invitations.isError && <div className="mt-4 divide-y rounded-xl border">
            {invitations.data?.map((invitation) => <div key={invitation.id} className="flex flex-wrap items-center gap-3 p-3">
              <div className="min-w-0 flex-1"><p className="truncate text-sm">{invitation.email}</p><p className="text-xs capitalize text-ink/40">{invitation.role} · {invitation.status}</p></div>
              {invitation.status === "pending" && <><button onClick={() => resendInvite.mutate(invitation.id)} className="rounded-lg p-2 hover:bg-muted" aria-label="Resend invitation"><RefreshCw size={15}/></button><button onClick={() => revokeInvite.mutate(invitation.id)} className="rounded-lg p-2 text-red-600 hover:bg-red-50" aria-label="Revoke invitation"><Trash2 size={15}/></button></>}
            </div>)}
          </div>}
        </div>}
      </section>}

      <section className="surface mt-6 border-red-200 p-5">
        <h2 className="font-medium text-red-700">Delete account</h2>
        <p className="mt-1 text-sm text-ink/50">Permanently delete your account and private owned content. This action cannot be undone.</p>
        <button onClick={() => { if (window.confirm("Permanently delete your DocMind account?")) deleteAccount.mutate(); }} disabled={deleteAccount.isPending} className="mt-4 rounded-xl border border-red-300 px-4 py-2 text-sm text-red-700 hover:bg-red-50">Delete account</button>
      </section>
    </div>
  );
}
