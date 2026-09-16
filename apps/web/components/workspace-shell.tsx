import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { CommandPalette } from "./command-palette";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-screen"><Sidebar/><div className="min-w-0 flex-1"><Topbar/><main className="h-[calc(100vh-4rem)] overflow-auto">{children}</main></div><CommandPalette/></div>;
}
