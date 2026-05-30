"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, GitBranch, Zap, Settings, BarChart3, Clock, Brain } from "lucide-react";

const navItems = [
  { href: "/", icon: MessageSquare, label: "Chat" },
  { href: "/workflow", icon: GitBranch, label: "Workflow" },
  { href: "/tasks", icon: Clock, label: "Tasks" },
  { href: "/skills", icon: Zap, label: "Skills" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/stats", icon: BarChart3, label: "Stats" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      style={{
        width: 240, height: "100vh", display: "flex", flexDirection: "column", flexShrink: 0,
        borderRight: "1px solid var(--color-border-default)",
        background: "var(--color-bg-secondary)",
      }}
    >
      <div style={{ padding: "24px 20px" }}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 14, textDecoration: "none" }}>
          <img src="/logo.png" alt="Logo" style={{ width: 38, height: 38, borderRadius: 10, objectFit: "cover" }} />
          <div>
            <span style={{ fontSize: 17, fontWeight: 700, color: "var(--color-text-primary)", display: "block" }}>KevinAgent</span>
            <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Self-evolving AI Agent</span>
          </div>
        </Link>
      </div>

      <nav style={{ flex: 1, padding: "6px 12px" }}>
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href} href={item.href}
              style={{
                display: "flex", alignItems: "center", gap: 14, padding: "12px 14px", borderRadius: 10,
                fontSize: 15, fontWeight: isActive ? 600 : 400, textDecoration: "none",
                color: isActive ? "var(--color-text-primary)" : "var(--color-text-muted)",
                background: isActive ? "var(--color-bg-elevated)" : "transparent",
                marginBottom: 4, transition: "all 0.15s ease", cursor: "pointer",
              }}
            >
              <item.icon size={20} strokeWidth={isActive ? 2 : 1.75} style={{ pointerEvents: "none" }} />
              <span style={{ pointerEvents: "none" }}>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--color-border-default)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--color-text-muted)" }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-success)", boxShadow: "0 0 8px rgba(34,197,94,0.4)" }} />
          System Online
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 6, opacity: 0.6 }}>
          v0.2.0
        </div>
      </div>
    </aside>
  );
}
