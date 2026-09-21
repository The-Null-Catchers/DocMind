"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";

import { api } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api<void>("/auth/password/reset", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border bg-panel p-6 shadow-sm">
        <div className="mb-7 flex items-center gap-2 font-semibold"><BookOpen size={22}/>DocMind</div>
        <h1 className="text-2xl font-semibold tracking-tight">{done ? "Password updated" : "Choose a new password"}</h1>
        {done ? (
          <>
            <p className="mt-3 text-sm text-ink/55">Your existing sessions were revoked. Sign in again with your new password.</p>
            <Link href="/login" className="mt-6 block rounded-xl bg-ink px-4 py-2.5 text-center text-sm font-medium text-panel">Sign in</Link>
          </>
        ) : (
          <>
            <label className="mt-7 block text-xs font-medium">New password
              <input type="password" minLength={10} required autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30"/>
            </label>
            <label className="mt-4 block text-xs font-medium">Confirm password
              <input type="password" minLength={10} required autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30"/>
            </label>
            {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
            {!token && <p className="mt-3 text-xs text-amber-700">Reset token is missing.</p>}
            <button disabled={busy || !token} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ink py-2.5 text-sm font-medium text-panel disabled:opacity-40">
              {busy && <Loader2 className="animate-spin" size={15}/>}Update password
            </button>
          </>
        )}
      </form>
    </main>
  );
}
