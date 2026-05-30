"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchTokenStats, fetchStatsOverview, fetchSandboxStatus, testSandbox, fetchContextStats } from "@/lib/api";
import { BarChart3, TrendingUp, Zap, Clock, Cpu, ShieldCheck, ShieldAlert, FlaskConical, Brain } from "lucide-react";

interface DailyStat {
  date: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
}

interface ModelStat {
  model: string;
  total_tokens: number;
  request_count: number;
}

interface ContextStats {
  config: {
    context_window_size: number;
    compression_enabled: boolean;
    compression_threshold: number;
    max_messages: number;
  };
  agents: {
    agent_id: string;
    model: string;
    provider: string;
    context_window: number;
    compression_enabled: boolean;
    compression_threshold: number;
    status: string;
    last_usage?: {
      estimated_tokens?: number;
      context_window?: number;
      usage_percent?: number;
      message_count?: number;
      max_messages?: number;
    };
  }[];
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

function MiniBarChart({ data, maxVal, color }: { data: number[]; maxVal: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 60 }}>
      {data.map((v, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: maxVal > 0 ? `${Math.max((v / maxVal) * 100, 2)}%` : "2%",
            background: color,
            borderRadius: 2,
            minWidth: 4,
            opacity: 0.85,
          }}
        />
      ))}
    </div>
  );
}

export default function StatsPage() {
  const [daily, setDaily] = useState<DailyStat[]>([]);
  const [byModel, setByModel] = useState<ModelStat[]>([]);
  const [overview, setOverview] = useState({ today: { total_tokens: 0, request_count: 0 }, week: { total_tokens: 0, request_count: 0 }, all_time: { total_tokens: 0, request_count: 0 } });
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [totals, setTotals] = useState({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, request_count: 0 });
  const [sandboxInfo, setSandboxInfo] = useState<{ enabled: boolean; backend: string; config?: Record<string, unknown> } | null>(null);
  const [sandboxTesting, setSandboxTesting] = useState(false);
  const [sandboxTestResult, setSandboxTestResult] = useState<Record<string, unknown> | null>(null);
  const [contextStats, setContextStats] = useState<ContextStats | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statsData, overviewData, sandboxData, contextData] = await Promise.all([
        fetchTokenStats(days).catch((e) => { console.error("fetchTokenStats error:", e); return { daily: [], by_model: [], totals: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, request_count: 0 } }; }),
        fetchStatsOverview().catch((e) => { console.error("fetchStatsOverview error:", e); return { today: { total_tokens: 0, request_count: 0 }, week: { total_tokens: 0, request_count: 0 }, all_time: { total_tokens: 0, request_count: 0 } }; }),
        fetchSandboxStatus().catch((e) => { console.error("fetchSandboxStatus error:", e); return null; }),
        fetchContextStats().catch((e) => { console.error("fetchContextStats error:", e); return null; }),
      ]);
      setDaily(statsData.daily || []);
      setByModel(statsData.by_model || []);
      setTotals(statsData.totals || { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, request_count: 0 });
      setOverview(overviewData);
      setSandboxInfo(sandboxData);
      setContextStats(contextData);
    } catch (e: any) {
      setError(e?.message || "Failed to load stats. Make sure the backend is running.");
    }
    setLoading(false);
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const maxTokens = Math.max(...daily.map((d) => d.total_tokens), 1);
  const maxRequests = Math.max(...daily.map((d) => d.request_count), 1);

  const statCardStyle: React.CSSProperties = {
    background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)",
    borderRadius: 14, padding: 20, flex: 1, minWidth: 0,
  };

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <header style={{ height: 56, borderBottom: "1px solid var(--color-border-default)", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, background: "var(--color-bg-elevated)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <BarChart3 size={20} color="var(--color-text-muted)" />
          <span style={{ fontSize: 17, fontWeight: 700 }}>Token Usage</span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {[7, 14, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)} style={{
              padding: "6px 14px", borderRadius: 8, fontSize: 13, cursor: "pointer", border: "none",
              background: days === d ? "var(--color-text-primary)" : "var(--color-bg-secondary)",
              color: days === d ? "var(--color-bg-primary)" : "var(--color-text-secondary)",
              fontWeight: days === d ? 600 : 400,
            }}>{d}d</button>
          ))}
        </div>
      </header>

      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "28px 24px" }}>
        {error && (
          <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 10, padding: "12px 16px", marginBottom: 20, fontSize: 14, color: "var(--color-error)" }}>{error}</div>
        )}
        {loading ? (
          <div style={{ textAlign: "center", padding: 80, color: "var(--color-text-muted)" }}>Loading...</div>
        ) : (
          <>
            {/* Overview Cards */}
            <div style={{ display: "flex", gap: 14, marginBottom: 28 }}>
              <div style={statCardStyle}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <Clock size={15} color="var(--color-info)" />
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>Today</span>
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--color-text-primary)" }}>{formatNumber(overview.today.total_tokens)}</div>
                <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: 4 }}>{overview.today.request_count} requests</div>
              </div>
              <div style={statCardStyle}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <TrendingUp size={15} color="var(--color-success)" />
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>7 Days</span>
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--color-text-primary)" }}>{formatNumber(overview.week.total_tokens)}</div>
                <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: 4 }}>{overview.week.request_count} requests</div>
              </div>
              <div style={statCardStyle}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <Zap size={15} color="var(--color-warning)" />
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>All Time</span>
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--color-text-primary)" }}>{formatNumber(overview.all_time.total_tokens)}</div>
                <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: 4 }}>{overview.all_time.request_count} requests</div>
              </div>
            </div>

            {/* Daily Chart */}
            <div style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 14, padding: 24, marginBottom: 28 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600 }}>Daily Token Usage</h3>
                <div style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--color-text-muted)" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-info)" }} /> Prompt</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-success)" }} /> Completion</span>
                </div>
              </div>
              {daily.length === 0 ? (
                <div style={{ textAlign: "center", padding: 40, color: "var(--color-text-muted)", fontSize: 14 }}>No data yet</div>
              ) : (
                <>
                  <div style={{ display: "flex", gap: 24, marginBottom: 16 }}>
                    <MiniBarChart data={daily.map((d) => d.prompt_tokens)} maxVal={maxTokens} color="var(--color-info)" />
                  </div>
                  <div style={{ display: "flex", gap: 24 }}>
                    <MiniBarChart data={daily.map((d) => d.completion_tokens)} maxVal={maxTokens} color="var(--color-success)" />
                  </div>
                  {/* Daily Table */}
                  <div style={{ marginTop: 20, maxHeight: 300, overflowY: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                          <th style={{ padding: "8px 12px", textAlign: "left", color: "var(--color-text-muted)", fontWeight: 600 }}>Date</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", color: "var(--color-info)", fontWeight: 600 }}>Prompt</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", color: "var(--color-success)", fontWeight: 600 }}>Completion</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", color: "var(--color-text-muted)", fontWeight: 600 }}>Total</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", color: "var(--color-text-muted)", fontWeight: 600 }}>Requests</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...daily].reverse().map((d) => (
                          <tr key={d.date} style={{ borderBottom: "1px solid var(--color-border-default)" }}>
                            <td style={{ padding: "8px 12px", color: "var(--color-text-secondary)" }}>{d.date}</td>
                            <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: "monospace" }}>{formatNumber(d.prompt_tokens)}</td>
                            <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: "monospace" }}>{formatNumber(d.completion_tokens)}</td>
                            <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: "monospace", fontWeight: 600 }}>{formatNumber(d.total_tokens)}</td>
                            <td style={{ padding: "8px 12px", textAlign: "right", fontFamily: "monospace" }}>{d.request_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>

            {/* By Model */}
            {byModel.length > 0 && (
              <div style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 14, padding: 24 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Usage by Model</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {byModel.map((m) => {
                    const pct = totals.total_tokens > 0 ? (m.total_tokens / totals.total_tokens) * 100 : 0;
                    return (
                      <div key={m.model} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: "var(--color-bg-secondary)", borderRadius: 10, border: "1px solid var(--color-border-default)" }}>
                        <Cpu size={14} color="var(--color-text-muted)" />
                        <span style={{ fontSize: 14, fontWeight: 500, minWidth: 140 }}>{m.model}</span>
                        <div style={{ flex: 1, height: 6, background: "var(--color-bg-elevated)", borderRadius: 3, overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${pct}%`, background: "var(--color-info)", borderRadius: 3, transition: "width 0.3s" }} />
                        </div>
                        <span style={{ fontSize: 13, fontFamily: "monospace", color: "var(--color-text-secondary)", minWidth: 70, textAlign: "right" }}>{formatNumber(m.total_tokens)}</span>
                        <span style={{ fontSize: 12, color: "var(--color-text-muted)", minWidth: 70, textAlign: "right" }}>{m.request_count} req</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Summary Footer */}
            <div style={{ marginTop: 20, padding: "14px 20px", background: "var(--color-bg-secondary)", borderRadius: 10, border: "1px solid var(--color-border-default)", display: "flex", gap: 20, fontSize: 13, color: "var(--color-text-muted)" }}>
              <span>Prompt tokens: <strong style={{ color: "var(--color-text-primary)" }}>{formatNumber(totals.prompt_tokens)}</strong></span>
              <span>Completion tokens: <strong style={{ color: "var(--color-text-primary)" }}>{formatNumber(totals.completion_tokens)}</strong></span>
              <span>Total: <strong style={{ color: "var(--color-text-primary)" }}>{formatNumber(totals.total_tokens)}</strong></span>
              <span>Requests: <strong style={{ color: "var(--color-text-primary)" }}>{totals.request_count}</strong></span>
            </div>

            {/* Context Usage */}
            {contextStats && (
              <div style={{ marginTop: 28, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 14, padding: 24 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
                  <Brain size={18} color="var(--color-info)" />
                  <h3 style={{ fontSize: 15, fontWeight: 600 }}>Context Window</h3>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                    <div style={{ ...statCardStyle, padding: "10px 16px" }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 4 }}>Window Size</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)" }}>{Number(contextStats.config.context_window_size || 0).toLocaleString()}</div>
                    </div>
                    <div style={{ ...statCardStyle, padding: "10px 16px" }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 4 }}>Max Messages</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)" }}>{contextStats.config.max_messages || 50}</div>
                    </div>
                    <div style={{ ...statCardStyle, padding: "10px 16px" }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 4 }}>Compression</div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: contextStats.config.compression_enabled ? "var(--color-success)" : "var(--color-error)" }}>
                        {contextStats.config.compression_enabled ? "Enabled" : "Disabled"}
                      </div>
                    </div>
                    <div style={{ ...statCardStyle, padding: "10px 16px" }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 4 }}>Compress Threshold</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)" }}>{Math.round(Number(contextStats.config.compression_threshold || 0.8) * 100)}%</div>
                    </div>
                  </div>
                  {contextStats.agents.map((agent) => (
                    <div key={agent.agent_id} style={{ padding: "10px 14px", background: "var(--color-bg-secondary)", borderRadius: 10, border: "1px solid var(--color-border-default)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <Cpu size={14} color="var(--color-text-muted)" />
                        <span style={{ fontSize: 14, fontWeight: 500, minWidth: 80 }}>{agent.agent_id}</span>
                        <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{agent.provider} / {agent.model}</span>
                        <span style={{ fontSize: 12, color: agent.compression_enabled ? "var(--color-success)" : "var(--color-text-muted)", marginLeft: "auto" }}>
                          {agent.compression_enabled ? "Auto-compress" : "No compression"}
                        </span>
                      </div>
                      {agent.last_usage && typeof agent.last_usage.usage_percent === "number" && (
                        <div style={{ marginTop: 10 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 11, color: "var(--color-text-muted)" }}>
                            <span>Last Context Usage</span>
                            <span>{agent.last_usage.usage_percent}%</span>
                          </div>
                          <div style={{ height: 6, background: "var(--color-bg-elevated)", borderRadius: 999, overflow: "hidden" }}>
                            <div
                              style={{
                                height: "100%",
                                width: `${Math.min(agent.last_usage.usage_percent, 100)}%`,
                                background: agent.last_usage.usage_percent >= agent.compression_threshold * 100 ? "var(--color-warning)" : "var(--color-info)",
                              }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No Data Help */}
            {overview.all_time.total_tokens === 0 && daily.length === 0 && (
              <div style={{ marginTop: 20, padding: "14px 20px", background: "rgba(56,189,248,0.06)", border: "1px solid rgba(56,189,248,0.2)", borderRadius: 10, fontSize: 13, color: "var(--color-info)", display: "flex", flexDirection: "column", gap: 6 }}>
                <strong>No token usage data found.</strong>
                <span>This typically means:</span>
                <ul style={{ marginLeft: 16, marginTop: 4 }}>
                  <li>No conversations have been completed yet</li>
                  <li>The backend&apos;s token_usage table might be empty</li>
                  <li>The LLM provider may not be returning usage data</li>
                </ul>
                <span>Try sending a message in Chat first, then refresh this page.</span>
              </div>
            )}

            {/* Sandbox Status */}
            {sandboxInfo && (
              <div style={{ marginTop: 28, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 14, padding: 24 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {sandboxInfo.enabled ? (
                      <ShieldCheck size={18} color="var(--color-success)" />
                    ) : (
                      <ShieldAlert size={18} color="var(--color-error)" />
                    )}
                    <h3 style={{ fontSize: 15, fontWeight: 600 }}>Sandbox Security</h3>
                  </div>
                  <button
                    onClick={async () => {
                      setSandboxTesting(true);
                      setSandboxTestResult(null);
                      try {
                        const result = await testSandbox();
                        setSandboxTestResult(result);
                      } catch (e) {
                        setSandboxTestResult({ success: false, error: String(e) });
                      }
                      setSandboxTesting(false);
                    }}
                    disabled={sandboxTesting}
                    style={{
                      padding: "6px 14px", borderRadius: 8, fontSize: 13, cursor: sandboxTesting ? "wait" : "pointer",
                      border: "1px solid var(--color-border-default)", background: "var(--color-bg-secondary)",
                      color: "var(--color-text-secondary)", display: "flex", alignItems: "center", gap: 6,
                    }}
                  >
                    <FlaskConical size={13} />
                    {sandboxTesting ? "Testing..." : "Test Sandbox"}
                  </button>
                </div>
                <div style={{ display: "flex", gap: 14, marginBottom: 16 }}>
                  <div style={{ ...statCardStyle, flex: "0 0 auto", padding: "14px 18px" }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Status</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: sandboxInfo.enabled ? "var(--color-success)" : "var(--color-error)", boxShadow: sandboxInfo.enabled ? "0 0 8px var(--color-success)" : "none" }} />
                      <span style={{ fontSize: 14, fontWeight: 600, color: sandboxInfo.enabled ? "var(--color-success)" : "var(--color-error)" }}>{sandboxInfo.enabled ? "Enabled" : "Disabled"}</span>
                    </div>
                  </div>
                  <div style={{ ...statCardStyle, flex: "0 0 auto", padding: "14px 18px" }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Backend</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>
                      {sandboxInfo.backend === "docker" ? "🐳 Docker" : sandboxInfo.backend === "local" ? "🔒 Local" : sandboxInfo.backend === "disabled" ? "⚠️ Disabled" : sandboxInfo.backend}
                    </div>
                  </div>
                  {sandboxInfo.config && (
                    <>
                      <div style={{ ...statCardStyle, flex: "0 0 auto", padding: "14px 18px" }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Memory</div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>{String(sandboxInfo.config.memory_limit || "512m")}</div>
                      </div>
                      <div style={{ ...statCardStyle, flex: "0 0 auto", padding: "14px 18px" }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>CPU Limit</div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>{String(sandboxInfo.config.cpu_limit || 1)} core</div>
                      </div>
                      <div style={{ ...statCardStyle, flex: "0 0 auto", padding: "14px 18px" }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Network</div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: sandboxInfo.config.network_disabled ? "var(--color-error)" : "var(--color-success)" }}>
                          {sandboxInfo.config.network_disabled ? "Blocked" : "Allowed"}
                        </div>
                      </div>
                    </>
                  )}
                </div>
                {sandboxTestResult && (
                  <div style={{ padding: "14px 18px", background: "var(--color-bg-secondary)", borderRadius: 10, border: "1px solid var(--color-border-default)", fontSize: 13 }}>
                    <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--color-text-secondary)" }}>Test Result:</div>
                    {Boolean(sandboxTestResult.shell_test) && (() => {
                      const st = sandboxTestResult.shell_test as Record<string, unknown>;
                      return (
                        <div style={{ marginBottom: 6 }}>
                          <span style={{ color: "var(--color-text-muted)" }}>Shell: </span>
                          <span style={{ color: st.success ? "var(--color-success)" : "var(--color-error)" }}>
                            {st.success ? "✓ PASS" : "✗ FAIL"}
                          </span>
                          {Boolean(st.output) && (
                            <pre style={{ fontSize: 12, marginTop: 4, padding: "6px 10px", background: "var(--color-bg-elevated)", borderRadius: 6, overflow: "auto" }}>
                              {String(st.output)}
                            </pre>
                          )}
                        </div>
                      );
                    })()}
                    {Boolean(sandboxTestResult.python_test) && (() => {
                      const pt = sandboxTestResult.python_test as Record<string, unknown>;
                      return (
                        <div>
                          <span style={{ color: "var(--color-text-muted)" }}>Python: </span>
                          <span style={{ color: pt.success ? "var(--color-success)" : "var(--color-error)" }}>
                            {pt.success ? "✓ PASS" : "✗ FAIL"}
                          </span>
                          {Boolean(pt.output) && (
                            <pre style={{ fontSize: 12, marginTop: 4, padding: "6px 10px", background: "var(--color-bg-elevated)", borderRadius: 6, overflow: "auto" }}>
                              {String(pt.output)}
                            </pre>
                          )}
                        </div>
                      );
                    })()}
                    {Boolean(sandboxTestResult.error) && (
                      <div style={{ color: "var(--color-error)" }}>Error: {String(sandboxTestResult.error)}</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
