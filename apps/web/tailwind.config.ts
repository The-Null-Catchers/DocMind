import type { Config } from "tailwindcss";
export default {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "hsl(var(--ink))",
        panel: "hsl(var(--panel))",
        line: "hsl(var(--line))",
        accent: "hsl(var(--accent))",
        muted: "hsl(var(--muted))"
      },
      boxShadow: { soft: "0 14px 40px rgba(0,0,0,.08)" }
    }
  },
  plugins: []
} satisfies Config;
