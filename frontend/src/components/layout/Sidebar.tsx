"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { MessageSquare, GitBranch, Zap, Settings, BarChart3, Clock, Brain, LogIn, LogOut, User } from "lucide-react";
import { getAuthToken, clearAuthToken } from "@/lib/api";

const navItems = [
  { href: "/", icon: MessageSquare, label: "Chat" },
  { href: "/workflow", icon: GitBranch, label: "Workflow" },
  { href: "/tasks", icon: Clock, label: "Tasks" },
  { href: "/skills", icon: Zap, label: "Skills" },
  { href: "/memory", icon: Brain, label: "Memory" },
  { href: "/stats", icon: BarChart3, label: "Stats" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

/** 应用侧边栏导航组件，负责渲染顶部品牌标识、主导航菜单以及底部用户状态区域（已登录显示头像与登出，未登录显示登录入口） */
export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState("");

  useEffect(() => {
    const token = getAuthToken();
    setIsAuthenticated(!!token);
    try {
      const info = localStorage.getItem("user_info");
      if (info) {
        const parsed = JSON.parse(info);
        setUserEmail(parsed.email || parsed.tenant_id?.slice(0, 12) || "");
      }
    } catch {}
  }, []);

  const handleLogout = () => {
    clearAuthToken();
    localStorage.removeItem("user_info");
    setIsAuthenticated(false);
    router.push("/login");
  };

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
        {isAuthenticated ? (
          <div
            onClick={handleLogout}
            title="Click to logout"
            style={{
              display: "flex", alignItems: "center", gap: 12, cursor: "pointer",
              padding: "6px 4px", borderRadius: 10, transition: "background 0.15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = "var(--color-bg-elevated, rgba(255,255,255,0.05))")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          >
            <div style={{
              width: 36, height: 36, borderRadius: "50%", flexShrink: 0,
              background: "var(--color-bg-elevated)",
              border: "1.5px solid var(--color-border-hover)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, fontWeight: 600, color: "var(--color-text-secondary)",
              letterSpacing: -0.5, position: "relative", overflow: "hidden",
            }}>
              <div style={{
                position: "absolute", inset: 0,
                background: "radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.06), transparent 60%)",
              }} />
              <span style={{ position: "relative" }}>
                {userEmail ? userEmail[0].toUpperCase() : "U"}
              </span>
            </div>
            <div style={{ overflow: "hidden", flex: 1 }}>
              <div style={{
                fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {userEmail || "User"}
              </div>
              <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 1 }}>
                Click to logout
              </div>
            </div>
          </div>
        ) : (
          <Link
            href="/login"
            style={{
              display: "flex", alignItems: "center", gap: 12, textDecoration: "none",
              padding: "6px 4px", borderRadius: 10, transition: "background 0.15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = "var(--color-bg-elevated, rgba(255,255,255,0.05))")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          >
            <div style={{
              width: 36, height: 36, borderRadius: "50%", flexShrink: 0,
              background: "var(--color-bg-elevated, #2a2a2a)",
              border: "2px dashed var(--color-border-default, #444)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <User size={16} style={{ color: "var(--color-text-muted)", opacity: 0.6 }} />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)" }}>
                Login / Register
              </div>
              <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 1 }}>
                Sign in to your account
              </div>
            </div>
          </Link>
        )}
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 10, opacity: 0.6 }}>
          v0.2.0
        </div>
      </div>
    </aside>
  );
}
