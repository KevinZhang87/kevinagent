"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchMemories, fetchMemoryStats, updateMemory, deleteMemory, cleanupMemories, fetchUserSettings } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Brain, Trash2, Edit3, Search, Save, X, Sparkles, AlertCircle, CheckCircle2, RefreshCw, Filter } from "lucide-react";

interface Memory {
  id: number;
  session_id: string;
  content: string;
  importance: number;
  type: string;
  created_at: string;
}

interface MemoryStats {
  total: number;
  by_type: Record<string, { count: number; avg_importance: number }>;
  sessions_with_memories: number;
  recent_24h: number;
}

const inputStyle: React.CSSProperties = {
  width: "100%", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
  borderRadius: 8, padding: "10px 14px", fontSize: 14, color: "var(--color-text-primary)", outline: "none",
};

const typeColors: Record<string, { bg: string; color: string }> = {
  general: { bg: "rgba(99,102,241,0.1)", color: "#818cf8" },
  skill: { bg: "rgba(34,197,94,0.1)", color: "#22c55e" },
  user_preference: { bg: "rgba(249,115,22,0.1)", color: "#f97316" },
  context_summary: { bg: "rgba(168,85,247,0.1)", color: "#a855f7" },
};

export default function MemoryPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editImportance, setEditImportance] = useState(0.5);
  const [editType, setEditType] = useState("general");
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [cleaningUp, setCleaningUp] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<string>("");
  const [cleanupDryRun, setCleanupDryRun] = useState(false);
  const [cleanupMaxAge, setCleanupMaxAge] = useState(30);
  const [cleanupMinImportance, setCleanupMinImportance] = useState(0.3);
  const [maintenanceInfo, setMaintenanceInfo] = useState({
    enabled: false,
    intervalHours: 12,
    lastCleanupAt: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [memData, statsData, settingsData] = await Promise.all([
        fetchMemories(undefined, filterType !== "all" ? filterType : undefined),
        fetchMemoryStats(),
        fetchUserSettings(),
      ]);
      setMemories(memData.memories || []);
      setStats(statsData);
      const settings = settingsData.settings || {};
      setMaintenanceInfo({
        enabled: String(settings.memory_auto_cleanup_enabled || "false").toLowerCase() === "true",
        intervalHours: Number(settings.memory_cleanup_interval_hours || 12),
        lastCleanupAt: settings.memory_last_cleanup_at || "",
      });
    } catch {}
    setLoading(false);
  }, [filterType]);

  useEffect(() => { load(); }, [load]);

  const handleSaveEdit = async () => {
    if (editingId === null) return;
    try {
      await updateMemory(editingId, { content: editContent, importance: editImportance, memory_type: editType });
      setEditingId(null);
      await load();
    } catch {}
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteMemory(id);
      setConfirmDelete(null);
      await load();
    } catch {}
  };

  const handleCleanup = async () => {
    setCleaningUp(true);
    setCleanupResult("");
    try {
      const result = await cleanupMemories(cleanupMaxAge, cleanupMinImportance, cleanupDryRun);
      if (cleanupDryRun) {
        setCleanupResult(`Dry run: ${result.deleted_count} memories would be cleaned up`);
      } else {
        setCleanupResult(`Cleaned up ${result.deleted_count} memories`);
        await load();
      }
    } catch (e: any) {
      setCleanupResult(`Cleanup failed: ${e.message}`);
    }
    setCleaningUp(false);
  };

  const filtered = memories.filter((m) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return m.content.toLowerCase().includes(q) || m.type.toLowerCase().includes(q);
    }
    return true;
  });

  const importanceColor = (imp: number) => {
    if (imp >= 0.8) return "var(--color-success)";
    if (imp >= 0.5) return "var(--color-warning)";
    return "var(--color-error)";
  };

  const statCardStyle: React.CSSProperties = {
    background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)",
    borderRadius: 10, padding: "14px 18px", flex: 1, minWidth: 0,
  };

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <header style={{ height: 56, borderBottom: "1px solid var(--color-border-default)", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, background: "var(--color-bg-elevated)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Brain size={20} color="var(--color-text-muted)" />
          <span style={{ fontSize: 17, fontWeight: 700 }}>Memory</span>
        </div>
        <button onClick={load} style={{ display: "flex", alignItems: "center", gap: 6, height: 32, padding: "0 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 8, fontSize: 13, color: "var(--color-text-secondary)", cursor: "pointer" }}>
          <RefreshCw size={13} /> Refresh
        </button>
      </header>

      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "28px 24px" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 80, color: "var(--color-text-muted)" }}>Loading...</div>
        ) : (
          <>
            {/* Stats Cards */}
            {stats && (
              <div style={{ display: "flex", gap: 14, marginBottom: 28 }}>
                <div style={statCardStyle}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Total Memories</div>
                  <div style={{ fontSize: 28, fontWeight: 700, color: "var(--color-text-primary)" }}>{stats.total}</div>
                </div>
                <div style={statCardStyle}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Sessions</div>
                  <div style={{ fontSize: 28, fontWeight: 700, color: "var(--color-info)" }}>{stats.sessions_with_memories}</div>
                </div>
                <div style={statCardStyle}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Last 24h</div>
                  <div style={{ fontSize: 28, fontWeight: 700, color: "var(--color-success)" }}>{stats.recent_24h}</div>
                </div>
                {Object.entries(stats.by_type).map(([type, info]) => (
                  <div key={type} style={statCardStyle}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>{type}</div>
                    <div style={{ fontSize: 28, fontWeight: 700, color: (typeColors[type] || typeColors.general).color }}>{info.count}</div>
                    <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>avg importance: {info.avg_importance}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Search & Filter */}
            <div style={{ display: "flex", gap: 10, marginBottom: 20, alignItems: "center" }}>
              <div style={{ flex: 1, position: "relative" }}>
                <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--color-text-muted)" }} />
                <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search memories..." style={{ ...inputStyle, paddingLeft: 34, fontSize: 13, height: 36 }} />
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {["all", "general", "skill", "user_preference", "context_summary"].map((f) => (
                  <button key={f} onClick={() => setFilterType(f)} style={{
                    padding: "6px 12px", borderRadius: 6, fontSize: 12, cursor: "pointer", border: "none",
                    background: filterType === f ? "var(--color-text-primary)" : "transparent",
                    color: filterType === f ? "var(--color-bg-primary)" : "var(--color-text-muted)",
                    fontWeight: filterType === f ? 600 : 400, textTransform: "capitalize",
                  }}>{f === "all" ? "All" : f.replace("_", " ")}</button>
                ))}
              </div>
            </div>

            {/* Auto Cleanup Section */}
            <div style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 14, padding: 20, marginBottom: 28 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                <Sparkles size={16} color="var(--color-warning)" />
                <h3 style={{ fontSize: 15, fontWeight: 600 }}>Auto Cleanup</h3>
              </div>
              <div style={{ marginBottom: 14, padding: "10px 12px", borderRadius: 10, background: "var(--color-bg-secondary)", border: "1px solid var(--color-border-default)", fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
                <div>自动维护状态: <strong style={{ color: maintenanceInfo.enabled ? "var(--color-success)" : "var(--color-text-muted)" }}>{maintenanceInfo.enabled ? "已开启" : "未开启"}</strong></div>
                <div>维护周期: 每 {maintenanceInfo.intervalHours} 小时</div>
                <div>{maintenanceInfo.lastCleanupAt ? `上次自动维护: ${new Date(maintenanceInfo.lastCleanupAt).toLocaleString()}` : "尚未执行自动维护"}</div>
              </div>
              <div style={{ display: "flex", gap: 14, alignItems: "end", flexWrap: "wrap" }}>
                <div>
                  <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Max age (days)</label>
                  <input type="number" value={cleanupMaxAge} onChange={(e) => setCleanupMaxAge(Number(e.target.value))} min={1} max={365} style={{ ...inputStyle, width: 80, fontSize: 13, padding: "6px 10px" }} />
                </div>
                <div>
                  <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 4 }}>Min importance</label>
                  <input type="number" value={cleanupMinImportance} onChange={(e) => setCleanupMinImportance(Number(e.target.value))} min={0} max={1} step={0.1} style={{ ...inputStyle, width: 80, fontSize: 13, padding: "6px 10px" }} />
                </div>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>
                  <input type="checkbox" checked={cleanupDryRun} onChange={(e) => setCleanupDryRun(e.target.checked)} style={{ accentColor: "var(--color-info)" }} />
                  Dry run
                </label>
                <button onClick={handleCleanup} disabled={cleaningUp} style={{ padding: "8px 16px", background: cleanupDryRun ? "var(--color-info)" : "var(--color-error)", color: "white", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", opacity: cleaningUp ? 0.5 : 1 }}>
                  {cleaningUp ? "Running..." : cleanupDryRun ? "Preview Cleanup" : "Cleanup Now"}
                </button>
              </div>
              {cleanupResult && (
                <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--color-bg-secondary)", borderRadius: 8, fontSize: 12, color: "var(--color-text-secondary)" }}>
                  {cleanupResult}
                </div>
              )}
            </div>

            {/* Memory List */}
            {filtered.length === 0 ? (
              <div style={{ textAlign: "center", padding: "80px 20px" }}>
                <div style={{ width: 48, height: 48, borderRadius: 14, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
                  <Brain size={22} color="var(--color-text-muted)" />
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>No memories yet</h3>
                <p style={{ fontSize: 14, color: "var(--color-text-muted)", maxWidth: 380, margin: "0 auto", lineHeight: 1.6 }}>
                  Memories are saved automatically by the agent during conversations. They help maintain context and learn from past interactions.
                </p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {filtered.map((m) => {
                  const tc = typeColors[m.type] || typeColors.general;
                  const isEditing = editingId === m.id;
                  return (
                    <div key={m.id} style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 10, padding: 16 }}>
                      <div style={{ display: "flex", alignItems: "start", gap: 12 }}>
                        {/* Importance bar */}
                        <div style={{ width: 4, height: 40, borderRadius: 2, background: importanceColor(m.importance), flexShrink: 0, marginTop: 2 }} />

                        <div style={{ flex: 1, minWidth: 0 }}>
                          {isEditing ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                              <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit", fontSize: 13 }} />
                              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                                <div>
                                  <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Importance</label>
                                  <input type="number" value={editImportance} onChange={(e) => setEditImportance(Number(e.target.value))} min={0} max={1} step={0.1} style={{ ...inputStyle, width: 70, fontSize: 12, padding: "4px 8px" }} />
                                </div>
                                <div>
                                  <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Type</label>
                                  <select value={editType} onChange={(e) => setEditType(e.target.value)} style={{ ...inputStyle, width: 140, fontSize: 12, padding: "4px 8px" }}>
                                    <option value="general">general</option>
                                    <option value="skill">skill</option>
                                    <option value="user_preference">user_preference</option>
                                    <option value="context_summary">context_summary</option>
                                  </select>
                                </div>
                                <button onClick={handleSaveEdit} style={{ padding: "4px 12px", background: "var(--color-success)", color: "white", border: "none", borderRadius: 6, fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                                  <Save size={12} /> Save
                                </button>
                                <button onClick={() => setEditingId(null)} style={{ padding: "4px 12px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, cursor: "pointer" }}>Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <p style={{ fontSize: 14, lineHeight: 1.6, color: "var(--color-text-primary)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{m.content}</p>
                              <div style={{ display: "flex", gap: 10, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
                                <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: tc.bg, color: tc.color, fontWeight: 500 }}>{m.type}</span>
                                <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Importance: {m.importance}</span>
                                <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Session: {m.session_id.slice(0, 8)}...</span>
                                <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{formatDate(m.created_at)}</span>
                              </div>
                            </>
                          )}
                        </div>

                        {!isEditing && (
                          <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                            <button onClick={() => { setEditingId(m.id); setEditContent(m.content); setEditImportance(m.importance); setEditType(m.type); }} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 4 }}>
                              <Edit3 size={14} />
                            </button>
                            {confirmDelete === m.id ? (
                              <div style={{ display: "flex", gap: 4 }}>
                                <button onClick={() => handleDelete(m.id)} style={{ padding: "2px 8px", fontSize: 11, background: "var(--color-error)", border: "none", borderRadius: 4, color: "white", cursor: "pointer" }}>Delete</button>
                                <button onClick={() => setConfirmDelete(null)} style={{ padding: "2px 8px", fontSize: 11, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 4, color: "var(--color-text-secondary)", cursor: "pointer" }}>Cancel</button>
                              </div>
                            ) : (
                              <button onClick={() => setConfirmDelete(m.id)} style={{ background: "none", border: "none", color: "var(--color-error)", cursor: "pointer", padding: 4, opacity: 0.5 }}>
                                <Trash2 size={14} />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
