"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, CircleCheck, CircleAlert, Loader2 } from "lucide-react";

import { api } from "@/lib/api";

export default function VerifyEmailPage() {
  const [state, setState] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Verifying your email…");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setState("error");
      setMessage("Verification token is missing.");
      return;
    }
    api<void>("/auth/email-verification/confirm", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then(() => {
        setState("success");
        setMessage("Your email address is verified.");
      })
      .catch((error) => {
        setState("error");
        setMessage(error instanceof Error ? error.message : "Email verification failed");
      });
  }, []);

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <div className="w-full max-w-sm rounded-2xl border bg-panel p-6 text-center shadow-sm">
        <div className="mb-7 flex items-center justify-center gap-2 font-semibold"><BookOpen size={22}/>DocMind</div>
        {state === "loading" && <Loader2 className="mx-auto animate-spin text-ink/40"/>}
        {state === "success" && <CircleCheck className="mx-auto text-emerald-600"/>}
        {state === "error" && <CircleAlert className="mx-auto text-red-600"/>}
        <h1 className="mt-4 text-xl font-semibold">{state === "success" ? "Email verified" : state === "error" ? "Verification failed" : "Verifying email"}</h1>
        <p className="mt-2 text-sm text-ink/55">{message}</p>
        <Link href={state === "success" ? "/app/settings" : "/login"} className="mt-6 block rounded-xl border px-4 py-2.5 text-sm hover:bg-muted">{state === "success" ? "Open settings" : "Back to sign in"}</Link>
      </div>
    </main>
  );
}
