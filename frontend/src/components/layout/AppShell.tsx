"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

const PUBLIC_PATHS = ["/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.includes(pathname);

  if (isPublic) {
    return <main style={{ height: "100vh", overflow: "hidden" }}>{children}</main>;
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar />
      <main style={{ flex: 1, overflow: "hidden", overflowY: "auto" }}>{children}</main>
    </div>
  );
}
