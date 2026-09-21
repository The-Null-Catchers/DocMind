"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, Loader2 } from "lucide-react";

import { api, storeSession } from "@/lib/api";

type AuthResult = { access_token: string; refresh_token: string };

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<AuthResult>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, device_name: "Web" }),
      });
      storeSession(result);
      router.push("/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <section className="hidden bg-ink p-12 text-panel lg:flex lg:flex-col">
        <div className="flex items-center gap-3 font-semibold"><BookOpen size={22}/>DocMind</div>
        <div className="my-auto max-w-xl">
          <p className="text-sm text-panel/50">YOUR KNOWLEDGE, GROUNDED</p>
          <h1 className="mt-5 text-5xl font-semibold leading-[1.06] tracking-[-.05em]">Read less.<br/>Understand more.<br/>Keep the source.</h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-panel/60">Search, compare, study, and chat across your documents with page-level citations you can verify instantly.</p>
        </div>
      </section>
      <section className="grid place-items-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><BookOpen/><span className="ms-2 font-semibold">DocMind</span></div>
          <h2 className="text-2xl font-semibold tracking-tight">Welcome back</h2>
          <p className="mt-1 text-sm text-ink/50">Continue your document workspace.</p>
          <label className="mt-7 block text-xs font-medium">Email
            <input type="email" required autoComplete="email" value={email} onChange={(e)=>setEmail(e.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30"/>
          </label>
          <div className="mt-4 flex items-center justify-between gap-3">
            <label className="text-xs font-medium">Password</label>
            <Link href="/forgot-password" className="text-xs font-medium text-ink/55 hover:text-ink">Forgot password?</Link>
          </div>
          <input type="password" required autoComplete="current-password" aria-label="Password" value={password} onChange={(e)=>setPassword(e.target.value)} className="mt-2 w-full rounded-xl border bg-panel px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-accent/30"/>
          {error && <p className="mt-3 text-xs text-red-500" role="alert">{error}</p>}
          <button disabled={busy} className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-ink py-2.5 text-sm font-medium text-panel disabled:opacity-60">
            {busy && <Loader2 className="animate-spin" size={15}/>}Sign in
          </button>
          <p className="mt-6 text-center text-xs text-ink/45">New to DocMind? <Link href="/register" className="font-medium text-ink">Create an account</Link></p>
        </form>
      </section>
    </main>
  );
}
