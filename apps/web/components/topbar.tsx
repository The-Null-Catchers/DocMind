"use client";

import { Command, Languages, Moon, Search, Sun, Upload } from "lucide-react";
import { useEffect } from "react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { useUI } from "@/store/ui";
import { messages } from "@/lib/i18n";

export function Topbar() {
  const { theme, setTheme } = useTheme();
  const { locale, setLocale, setCommandOpen } = useUI();
  const t = messages[locale];
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setCommandOpen(true); }
    };
    window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler);
  }, [setCommandOpen]);
  useEffect(() => { document.documentElement.dir = locale === "ar" ? "rtl" : "ltr"; document.documentElement.lang = locale; }, [locale]);
  return (
    <header className="flex h-16 items-center gap-3 border-b bg-panel/85 px-5 backdrop-blur">
      <button onClick={() => setCommandOpen(true)} className="focus-ring flex min-w-0 max-w-xl flex-1 items-center gap-3 rounded-xl border bg-muted/40 px-3 py-2 text-sm text-ink/50"><Search size={16}/><span className="truncate">{t.search}</span><span className="ms-auto hidden rounded border bg-panel px-1.5 py-0.5 text-[10px] sm:inline">⌘K</span></button>
      <Button className="bg-ink text-panel hover:bg-ink/90"><Upload size={16}/><span className="hidden sm:inline">{t.upload}</span></Button>
      <Button aria-label="Switch language" onClick={() => setLocale(locale === "en" ? "ar" : "en")}><Languages size={17}/><span className="text-xs">{locale.toUpperCase()}</span></Button>
      <Button aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun size={17}/> : <Moon size={17}/>}</Button>
    </header>
  );
}
