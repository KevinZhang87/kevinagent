"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { register, login, setAuthToken } from "@/lib/api";
import { User, Mail, Lock, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let data;
      if (mode === "register") {
        data = await register(email, password, name || undefined);
      } else {
        data = await login(email, password);
      }
      setAuthToken(data.access_token);
      localStorage.setItem("user_info", JSON.stringify({
        user_id: data.user_id,
        tenant_id: data.tenant_id,
        role: data.role,
        email: email,
      }));
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "11px 14px 11px 40px",
    borderRadius: 10,
    border: "1px solid var(--color-border-default)",
    backgroundColor: "var(--color-bg-primary)",
    color: "var(--color-text-primary)",
    fontSize: 14,
    outline: "none",
    boxSizing: "border-box",
    transition: "border-color 0.15s",
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    marginBottom: 6,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--color-text-secondary)",
  };

  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      minHeight: "100vh",
      background: "var(--color-bg-primary)",
    }}>
      <div style={{ width: 380, padding: "0 24px" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16, margin: "0 auto 16px",
            background: "var(--color-bg-card)",
            border: "1px solid var(--color-border-default)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 22, fontWeight: 700, color: "var(--color-text-primary)",
            position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", inset: 0,
              background: "radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.08), transparent 60%)",
            }} />
            <span style={{ position: "relative" }}>K</span>
          </div>
          <h1 style={{
            fontSize: 22, fontWeight: 700, color: "var(--color-text-primary)",
            margin: 0, letterSpacing: -0.5,
          }}>
            KevinAgent
          </h1>
          <p style={{
            fontSize: 13, color: "var(--color-text-muted)", margin: "6px 0 0",
          }}>
            Self-evolving AI Agent Framework
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: "var(--color-bg-card)",
          border: "1px solid var(--color-border-default)",
          borderRadius: 14,
          padding: "28px 24px",
        }}>
          {/* Toggle */}
          <div style={{
            display: "flex", marginBottom: 24, borderRadius: 10, overflow: "hidden",
            border: "1px solid var(--color-border-default)",
            background: "var(--color-bg-primary)",
          }}>
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(""); }}
                style={{
                  flex: 1, padding: "9px 0", border: "none", cursor: "pointer",
                  fontSize: 13, fontWeight: 500, transition: "all 0.15s",
                  background: mode === m ? "var(--color-bg-elevated)" : "transparent",
                  color: mode === m ? "var(--color-text-primary)" : "var(--color-text-muted)",
                }}
              >
                {m === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit}>
            {mode === "register" && (
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Workspace Name</label>
                <div style={{ position: "relative" }}>
                  <User size={15} style={{
                    position: "absolute", left: 13, top: "50%", transform: "translateY(-50%)",
                    color: "var(--color-text-muted)", pointerEvents: "none",
                  }} />
                  <input
                    type="text" value={name} onChange={(e) => setName(e.target.value)}
                    placeholder="My Workspace (optional)"
                    style={inputStyle}
                    onFocus={e => e.target.style.borderColor = "var(--color-border-hover)"}
                    onBlur={e => e.target.style.borderColor = "var(--color-border-default)"}
                  />
                </div>
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Email</label>
              <div style={{ position: "relative" }}>
                <Mail size={15} style={{
                  position: "absolute", left: 13, top: "50%", transform: "translateY(-50%)",
                  color: "var(--color-text-muted)", pointerEvents: "none",
                }} />
                <input
                  type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com" required
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = "var(--color-border-hover)"}
                  onBlur={e => e.target.style.borderColor = "var(--color-border-default)"}
                />
              </div>
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={labelStyle}>Password</label>
              <div style={{ position: "relative" }}>
                <Lock size={15} style={{
                  position: "absolute", left: 13, top: "50%", transform: "translateY(-50%)",
                  color: "var(--color-text-muted)", pointerEvents: "none",
                }} />
                <input
                  type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 6 characters" required minLength={6}
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = "var(--color-border-hover)"}
                  onBlur={e => e.target.style.borderColor = "var(--color-border-default)"}
                />
              </div>
            </div>

            {error && (
              <div style={{
                padding: "10px 14px", marginBottom: 16, borderRadius: 10,
                background: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.2)",
                color: "var(--color-error)", fontSize: 13,
              }}>
                {error}
              </div>
            )}

            <button
              type="submit" disabled={loading}
              style={{
                width: "100%", padding: "11px 0", borderRadius: 10, border: "none",
                background: loading ? "var(--color-bg-hover)" : "var(--color-text-primary)",
                color: loading ? "var(--color-text-muted)" : "var(--color-bg-primary)",
                fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                transition: "all 0.15s",
              }}
            >
              {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
              {!loading && <ArrowRight size={16} />}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p style={{
          textAlign: "center", fontSize: 12, color: "var(--color-text-muted)",
          marginTop: 20, opacity: 0.5,
        }}>
          v0.2.0
        </p>
      </div>
    </div>
  );
}
