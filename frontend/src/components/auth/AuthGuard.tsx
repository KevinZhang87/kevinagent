"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { getAuthToken } from "@/lib/api";

const PUBLIC_PATHS = ["/login"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (PUBLIC_PATHS.includes(pathname)) {
      setChecked(true);
      return;
    }
    const token = getAuthToken();
    if (!token) {
      router.replace("/login");
    } else {
      setChecked(true);
    }
  }, [pathname, router]);

  // Public pages always render immediately
  if (PUBLIC_PATHS.includes(pathname)) {
    return <>{children}</>;
  }

  // Don't flash protected content before auth check completes
  if (!checked) {
    return (
      <div style={{
        display: "flex", justifyContent: "center", alignItems: "center",
        height: "100vh", background: "var(--color-bg-primary)",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%", margin: "0 auto 16px",
            border: "3px solid var(--color-border-default)",
            borderTopColor: "var(--color-text-muted)",
            animation: "spin 0.8s linear infinite",
          }} />
          <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>Loading...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
