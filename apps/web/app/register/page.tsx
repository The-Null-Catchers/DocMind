"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";

import { api, storeSession } from "@/lib/api";

type AuthResult = { access_token: string; refresh_token: string };

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<AuthResult>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, display_name: name, locale: "en" }),
      });
      storeSession(result);
      router.push("/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border bg-panel p-6 shadow-sm">
        <div className="mb-7 flex items-center gap-2 font-semibold"><BookOpen size={22}/>DocMind</div>
        <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
        <p className="mt-1 text-sm text-ink/50">Start with a private document workspace.</p>
        <label className="mt-7 block text-xs font-medium">Display name
          <input required value={name} onChange={(e)=>setName(e.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30" />
        </label>
        <label className="mt-4 block text-xs font-medium">Email
          <input type="email" required autoComplete="email" value={email} onChange={(e)=>setEmail(e.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30" />
        </label>
        <label className="mt-4 block text-xs font-medium">Password
          <input type="password" minLength={10} required autoComplete="new-password" value={password} onChange={(e)=>setPassword(e.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30" />
        </label>
        {error && <p className="mt-3 text-xs text-red-500" role="alert">{error}</p>}
        <button disabled={busy} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ink py-2.5 text-sm font-medium text-panel disabled:opacity-60">
          {busy && <Loader2 className="animate-spin" size={15}/>}Create account
        </button>
        <p className="mt-6 text-center text-xs text-ink/45">Already have an account? <Link className="font-medium text-ink" href="/login">Sign in</Link></p>
      </form>
    </main>
  );
}
