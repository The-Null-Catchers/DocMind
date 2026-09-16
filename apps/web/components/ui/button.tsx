import clsx from "clsx";
import type { ButtonHTMLAttributes } from "react";

export function Button({ className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={clsx("focus-ring inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition hover:bg-muted disabled:opacity-50", className)} {...props}>{children}</button>;
}
