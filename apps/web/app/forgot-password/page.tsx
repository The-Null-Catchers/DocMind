"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";

import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [devToken, setDevToken] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setDevToken(null);
    try {
      const result = await api<{ message: string; dev_token?: string }>("/auth/password/forgot", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setMessage(result.message);
      setDevToken(result.dev_token ?? null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not request password reset");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border bg-panel p-6 shadow-sm">
        <div className="mb-7 flex items-center gap-2 font-semibold"><BookOpen size={22}/>DocMind</div>
        <h1 className="text-2xl font-semibold tracking-tight">Reset your password</h1>
        <p className="mt-1 text-sm text-ink/50">Enter your account email to request reset instructions.</p>
        <label className="mt-7 block text-xs font-medium">Email
          <input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30"/>
        </label>
        <button disabled={busy} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ink py-2.5 text-sm font-medium text-panel disabled:opacity-60">
          {busy && <Loader2 className="animate-spin" size={15}/>}Request reset
        </button>
        {message && <p className="mt-4 text-sm text-ink/60">{message}</p>}
        {devToken && <Link href={`/reset-password?token=${encodeURIComponent(devToken)}`} className="mt-3 block rounded-xl border px-3 py-2 text-center text-sm hover:bg-muted">Continue with development token</Link>}
        <p className="mt-6 text-center text-xs text-ink/45"><Link href="/login" className="font-medium text-ink">Back to sign in</Link></p>
      </form>
    </main>
  );
}
