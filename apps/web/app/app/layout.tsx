import { WorkspaceShell } from "@/components/workspace-shell";
import { QueryProvider } from "../providers";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <WorkspaceShell>{children}</WorkspaceShell>
    </QueryProvider>
  );
}
