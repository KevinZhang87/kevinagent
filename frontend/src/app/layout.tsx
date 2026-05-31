import type { Metadata } from "next";
import "@/styles/globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { AppProvider } from "@/contexts/AppContext";

export const metadata: Metadata = {
  title: "KevinAgent",
  description: "Self-evolving AI Agent Framework",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body style={{ margin: 0, padding: 0 }}>
        <AppProvider>
          <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
            <Sidebar />
            <main style={{ flex: 1, overflow: "hidden", overflowY: "auto" }}>{children}</main>
          </div>
        </AppProvider>
      </body>
    </html>
  );
}
