"use client";

import { useState, useEffect } from "react";
import { Check, AlertTriangle, Plus, X, Save, Palette, User, Bot, Brain, Database } from "lucide-react";
import { fetchProviders, fetchCurrentConfig, saveSettings, addCustomModel, removeCustomModel, fetchUserSettings, updateUserSettings } from "@/lib/api";
import { useApp } from "@/contexts/AppContext";

interface ModelInfo { id: string; name: string; }
interface Provider { name: string; id: string; models: ModelInfo[]; is_configured: boolean; }

const inputStyle: React.CSSProperties = {
  width: "100%", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
  borderRadius: 8, padding: "10px 14px", fontSize: 14, color: "var(--color-text-primary)", outline: "none",
};

const btnSmall: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 4, height: 30, padding: "0 10px",
  background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
  borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer",
};

const themes = [
  { id: "dark", name: "Dark", bg: "#16161a", card: "#1e1e22", text: "#e2e2e6" },
  { id: "midnight", name: "Midnight", bg: "#0d1117", card: "#161b22", text: "#c9d1d9" },
  { id: "warm", name: "Warm Dark", bg: "#1c1917", card: "#292524", text: "#e7e5e4" },
  { id: "ocean", name: "Ocean", bg: "#0f172a", card: "#1e293b", text: "#e2e8f0" },
];

const bgOptions = [
  { id: "none", name: "None" },
  { id: "grid", name: "Grid Pattern" },
  { id: "dots", name: "Dot Pattern" },
  { id: "gradient1", name: "Gradient Blue" },
  { id: "gradient2", name: "Gradient Purple" },
];

export default function SettingsPage() {
  const { refreshProviders } = useApp();
  const [allProviders, setAllProviders] = useState<Provider[]>([]);
  const [activeIds, setActiveIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [baseUrls, setBaseUrls] = useState<Record<string, string>>({});
  const [defaultProvider, setDefaultProvider] = useState("openai");
  const [defaultModel, setDefaultModel] = useState("gpt-4o");
  const [maxIterations, setMaxIterations] = useState(30);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [showAddModel, setShowAddModel] = useState<string | null>(null);
  const [newModelName, setNewModelName] = useState("");

  // User settings
  const [theme, setTheme] = useState("dark");
  const [background, setBackground] = useState("none");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [agentRole, setAgentRole] = useState("");
  const [contextWindowSize, setContextWindowSize] = useState(128000);
  const [contextCompressionEnabled, setContextCompressionEnabled] = useState(true);
  const [contextCompressionThreshold, setContextCompressionThreshold] = useState(0.8);
  const [contextMaxMessages, setContextMaxMessages] = useState(50);
  const [autoEvolve, setAutoEvolve] = useState(true);
  const [evolveThreshold, setEvolveThreshold] = useState(3);
  const [memoryAutoCleanupEnabled, setMemoryAutoCleanupEnabled] = useState(true);
  const [memoryCleanupMaxAgeDays, setMemoryCleanupMaxAgeDays] = useState(30);
  const [memoryCleanupMinImportance, setMemoryCleanupMinImportance] = useState(0.3);
  const [memoryCleanupIntervalHours, setMemoryCleanupIntervalHours] = useState(12);

  // Memory backend config
  const [memoryBackend, setMemoryBackend] = useState("sqlite");
  const [memVectorProvider, setMemVectorProvider] = useState("qdrant");
  const [memVectorHost, setMemVectorHost] = useState("localhost");
  const [memVectorPort, setMemVectorPort] = useState(6333);
  const [memLlmProvider, setMemLlmProvider] = useState("openai");
  const [memLlmModel, setMemLlmModel] = useState("gpt-4o-mini");
  const [memEmbedderProvider, setMemEmbedderProvider] = useState("openai");
  const [memEmbedderModel, setMemEmbedderModel] = useState("text-embedding-3-small");

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      // Refresh shared context so chat page has latest data
      await refreshProviders();

      const d = await fetchProviders();
      const list: Provider[] = d.providers || [];
      setAllProviders(list);

      try {
        const cfg = await fetchCurrentConfig();
        if (cfg.provider) setDefaultProvider(cfg.provider);
        if (cfg.model) setDefaultModel(cfg.model);
        if (cfg.active_providers) setActiveIds(cfg.active_providers);
        if (cfg.providers) {
          const urls: Record<string, string> = {};
          for (const [pid, info] of Object.entries(cfg.providers as Record<string, { base_url: string }>)) {
            urls[pid] = info.base_url || "";
          }
          setBaseUrls(urls);
        }
        // Memory backend config
        if (cfg.memory_backend) setMemoryBackend(cfg.memory_backend);
        const mc = cfg.memory_config || {};
        if (mc.vector_store) {
          if (mc.vector_store.provider) setMemVectorProvider(mc.vector_store.provider);
          if (mc.vector_store.host) setMemVectorHost(mc.vector_store.host);
          if (mc.vector_store.port) setMemVectorPort(mc.vector_store.port);
        }
        if (mc.llm) {
          if (mc.llm.provider) setMemLlmProvider(mc.llm.provider);
          if (mc.llm.model) setMemLlmModel(mc.llm.model);
        }
        if (mc.embedder) {
          if (mc.embedder.provider) setMemEmbedderProvider(mc.embedder.provider);
          if (mc.embedder.model) setMemEmbedderModel(mc.embedder.model);
        }
      } catch {}

      // Load user settings
      try {
        const us = await fetchUserSettings();
        const s = us.settings || {};
        if (s.theme) setTheme(s.theme);
        if (s.background) setBackground(s.background);
        if (s.avatar_url) setAvatarUrl(s.avatar_url);
        if (s.agent_role) setAgentRole(s.agent_role);
        if (s.context_window_size) setContextWindowSize(Number(s.context_window_size));
        if (s.context_compression_enabled !== undefined) setContextCompressionEnabled(s.context_compression_enabled === "true");
        if (s.context_compression_threshold) setContextCompressionThreshold(Number(s.context_compression_threshold));
        if (s.context_max_messages) setContextMaxMessages(Number(s.context_max_messages));
        if (s.auto_evolve !== undefined) setAutoEvolve(s.auto_evolve === "true");
        if (s.evolve_threshold) setEvolveThreshold(Number(s.evolve_threshold));
        if (s.memory_auto_cleanup_enabled !== undefined) setMemoryAutoCleanupEnabled(s.memory_auto_cleanup_enabled === "true");
        if (s.memory_cleanup_max_age_days) setMemoryCleanupMaxAgeDays(Number(s.memory_cleanup_max_age_days));
        if (s.memory_cleanup_min_importance) setMemoryCleanupMinImportance(Number(s.memory_cleanup_min_importance));
        if (s.memory_cleanup_interval_hours) setMemoryCleanupIntervalHours(Number(s.memory_cleanup_interval_hours));
        // Apply theme immediately
        applyTheme(s.theme || "dark");
        applyBackground(s.background || "none");
      } catch {}
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally { setLoading(false); }
  };

  const applyTheme = (themeId: string) => {
    const t = themes.find((x) => x.id === themeId) || themes[0];
    document.documentElement.style.setProperty("--color-bg-primary", t.bg);
    document.documentElement.style.setProperty("--color-bg-card", t.card);
    document.documentElement.style.setProperty("--color-bg-secondary", t.card);
    document.documentElement.style.setProperty("--color-bg-elevated", t.card);
    document.documentElement.style.setProperty("--color-text-primary", t.text);
  };

  const applyBackground = (bgId: string) => {
    const body = document.body;
    body.style.backgroundImage = "";
    body.style.backgroundSize = "";
    body.style.backgroundPosition = "";
    if (bgId === "grid") {
      body.style.backgroundImage = "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)";
      body.style.backgroundSize = "40px 40px";
    } else if (bgId === "dots") {
      body.style.backgroundImage = "radial-gradient(rgba(255,255,255,0.06) 1px, transparent 1px)";
      body.style.backgroundSize = "24px 24px";
    } else if (bgId === "gradient1") {
      body.style.backgroundImage = "radial-gradient(ellipse at 20% 50%, rgba(56,189,248,0.08) 0%, transparent 50%), radial-gradient(ellipse at 80% 50%, rgba(99,102,241,0.08) 0%, transparent 50%)";
      body.style.backgroundSize = "100% 100%";
    } else if (bgId === "gradient2") {
      body.style.backgroundImage = "radial-gradient(ellipse at 20% 50%, rgba(168,85,247,0.08) 0%, transparent 50%), radial-gradient(ellipse at 80% 50%, rgba(236,72,153,0.08) 0%, transparent 50%)";
      body.style.backgroundSize = "100% 100%";
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      // If no provider selected, use the first active provider
      let finalProvider = defaultProvider;
      let finalModel = defaultModel;

      if (!finalProvider && activeProviders.length > 0) {
        finalProvider = activeProviders[0].id;
        if (activeProviders[0].models.length > 0) {
          finalModel = activeProviders[0].models[0].id;
        }
      }

      const data = await saveSettings({
        api_keys: apiKeys,
        base_urls: baseUrls,
        default_provider: finalProvider,
        default_model: finalModel,
        max_iterations: maxIterations,
        active_providers: activeIds,
        memory_backend: memoryBackend,
        memory_config: memoryBackend === "mem0" ? {
          vector_store: { provider: memVectorProvider, host: memVectorHost, port: memVectorPort },
          llm: { provider: memLlmProvider, model: memLlmModel },
          embedder: { provider: memEmbedderProvider, model: memEmbedderModel },
        } : {},
      });
      if (data.status === "ok") {
        // Save user settings
        await updateUserSettings({
          theme,
          background,
          avatar_url: avatarUrl,
          agent_role: agentRole,
          context_window_size: String(contextWindowSize),
          context_compression_enabled: String(contextCompressionEnabled),
          context_compression_threshold: String(contextCompressionThreshold),
          context_max_messages: String(contextMaxMessages),
          auto_evolve: String(autoEvolve),
          evolve_threshold: String(evolveThreshold),
          memory_auto_cleanup_enabled: String(memoryAutoCleanupEnabled),
          memory_cleanup_max_age_days: String(memoryCleanupMaxAgeDays),
          memory_cleanup_min_importance: String(memoryCleanupMinImportance),
          memory_cleanup_interval_hours: String(memoryCleanupIntervalHours),
        });
        applyTheme(theme);
        applyBackground(background);
        // Refresh providers in shared context so Chat page picks up changes
        await refreshProviders();
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        await load();
      }
      else setError(data.message || "Save failed");
    } catch (e) { setError(e instanceof Error ? e.message : "Save failed"); }
    finally { setSaving(false); }
  };

  const addProvider = (id: string) => {
    if (!activeIds.includes(id)) setActiveIds((prev) => [...prev, id]);
    setShowAddMenu(false);
  };

  const removeProvider = (id: string) => {
    setActiveIds((prev) => prev.filter((x) => x !== id));
  };

  const handleAddCustomModel = async (providerId: string) => {
    const name = newModelName.trim();
    if (!name) return;
    try {
      // Model name serves as both id and display name (mainstream approach)
      await addCustomModel(providerId, name, name);
      setShowAddModel(null);
      setNewModelName("");
      await refreshProviders();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add model");
    }
  };

  const handleRemoveCustomModel = async (providerId: string, modelId: string) => {
    try {
      await removeCustomModel(providerId, modelId);
      await refreshProviders();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove model");
    }
  };

  const activeProviders = allProviders.filter((p) => activeIds.includes(p.id));
  const availableToAdd = allProviders.filter((p) => !activeIds.includes(p.id));

  const sectionTitle: React.CSSProperties = { fontSize: 17, fontWeight: 700, marginBottom: 20, display: "flex", alignItems: "center", gap: 10 };

  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <header style={{ height: 56, borderBottom: "1px solid var(--color-border-default)", padding: "0 24px", display: "flex", alignItems: "center", flexShrink: 0, background: "var(--color-bg-elevated)" }}>
        <span style={{ fontSize: 17, fontWeight: 700 }}>Settings</span>
      </header>
      <div style={{ maxWidth: 680, margin: "0 auto", padding: "32px 24px" }}>
        {error && <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 10, padding: "12px 16px", marginBottom: 20, fontSize: 14, color: "var(--color-error)" }}>{error}</div>}
        {saved && <div style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)", borderRadius: 10, padding: "12px 16px", marginBottom: 20, fontSize: 14, color: "var(--color-success)", display: "flex", alignItems: "center", gap: 8 }}><Check size={15} /> Settings saved successfully</div>}

        {/* Appearance */}
        <section style={{ marginBottom: 40 }}>
          <h2 style={sectionTitle}><Palette size={18} /> Appearance</h2>
          <div style={{ border: "1px solid var(--color-border-default)", borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 20, background: "var(--color-bg-card)" }}>
            {/* Theme */}
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 12 }}>Theme</label>
              <div style={{ display: "flex", gap: 10 }}>
                {themes.map((t) => (
                  <button key={t.id} onClick={() => setTheme(t.id)} style={{
                    flex: 1, padding: 14, borderRadius: 10, cursor: "pointer",
                    border: theme === t.id ? "2px solid var(--color-info)" : "1px solid var(--color-border-default)",
                    background: t.bg, display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                  }}>
                    <div style={{ width: 40, height: 24, borderRadius: 6, background: t.card, border: "1px solid rgba(255,255,255,0.1)" }} />
                    <span style={{ fontSize: 12, color: t.text, fontWeight: theme === t.id ? 600 : 400 }}>{t.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Background */}
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 12 }}>Background</label>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {bgOptions.map((b) => (
                  <button key={b.id} onClick={() => setBackground(b.id)} style={{
                    padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13,
                    border: background === b.id ? "2px solid var(--color-info)" : "1px solid var(--color-border-default)",
                    background: background === b.id ? "var(--color-bg-elevated)" : "var(--color-bg-secondary)",
                    color: background === b.id ? "var(--color-text-primary)" : "var(--color-text-muted)",
                    fontWeight: background === b.id ? 600 : 400,
                  }}>{b.name}</button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Profile */}
        <section style={{ marginBottom: 40 }}>
          <h2 style={sectionTitle}><User size={18} /> Profile</h2>
          <div style={{ border: "1px solid var(--color-border-default)", borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 20, background: "var(--color-bg-card)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ width: 64, height: 64, borderRadius: 16, background: "var(--color-bg-secondary)", border: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", flexShrink: 0 }}>
                {avatarUrl ? <img src={avatarUrl} alt="Avatar" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <User size={24} color="var(--color-text-muted)" />}
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 8 }}>Avatar URL</label>
                <input type="text" value={avatarUrl} onChange={(e) => setAvatarUrl(e.target.value)} placeholder="https://example.com/avatar.png" style={{ ...inputStyle, fontSize: 13 }} />
              </div>
            </div>
          </div>
        </section>

        {/* Agent Role */}
        <section style={{ marginBottom: 40 }}>
          <h2 style={sectionTitle}><Bot size={18} /> Agent Configuration</h2>
          <div style={{ border: "1px solid var(--color-border-default)", borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 20, background: "var(--color-bg-card)" }}>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Agent Role / System Prompt</label>
              <textarea value={agentRole} onChange={(e) => setAgentRole(e.target.value)} placeholder="Customize the agent's personality and role. Leave empty to use the default system prompt." rows={4} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit", minHeight: 100 }} />
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>This will be prepended to the agent&apos;s system prompt</p>
            </div>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Default Provider</label>
              <select value={defaultProvider} onChange={(e) => {
                setDefaultProvider(e.target.value);
                // Auto-select first model when provider changes
                const selectedProvider = activeProviders.find(p => p.id === e.target.value);
                if (selectedProvider && selectedProvider.models.length > 0) {
                  setDefaultModel(selectedProvider.models[0].id);
                } else {
                  setDefaultModel("");
                }
              }} style={inputStyle}>
                <option value="">-- Auto (first configured) --</option>
                {activeProviders.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>
                {activeProviders.length === 0
                  ? "No providers configured. Please add a provider first."
                  : activeProviders.length === 1
                    ? "Only one provider configured. It will be used as default."
                    : "Select which provider to use as default. If not selected, the first configured provider will be used."}
              </p>
            </div>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Default Model</label>
              <select
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                style={inputStyle}
                disabled={!defaultProvider}
              >
                <option value="">-- Auto (first model) --</option>
                {defaultProvider && activeProviders
                  .find(p => p.id === defaultProvider)
                  ?.models.map((m) => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  )) || []}
              </select>
              {!defaultProvider && activeProviders.length > 0 && (
                <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>
                  No provider selected. The first model of the first configured provider will be used.
                </p>
              )}
            </div>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Max Iterations (agent loop)</label>
              <input type="number" value={maxIterations} onChange={(e) => setMaxIterations(Number(e.target.value))} min={1} max={100} style={inputStyle} />
            </div>
          </div>
        </section>

        {/* Context Configuration */}
        <section style={{ marginBottom: 40 }}>
          <h2 style={sectionTitle}><Brain size={18} /> Context Configuration</h2>
          <div style={{ border: "1px solid var(--color-border-default)", borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 20, background: "var(--color-bg-card)" }}>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Context Window Size (tokens)</label>
              <input type="number" value={contextWindowSize} onChange={(e) => setContextWindowSize(Number(e.target.value))} min={2048} max={2000000} step={1000} style={inputStyle} />
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>Maximum token count for the LLM context window. Common values: 8k, 32k, 128k, 200k. 保存后会立即应用到新的上下文计算。</p>
            </div>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Max Messages in Context</label>
              <input type="number" value={contextMaxMessages} onChange={(e) => setContextMaxMessages(Number(e.target.value))} min={5} max={200} style={inputStyle} />
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>Maximum number of messages kept in the active prompt before older content is compressed or trimmed</p>
            </div>
            <div>
              <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--color-text-muted)", cursor: "pointer" }}>
                <input type="checkbox" checked={contextCompressionEnabled} onChange={(e) => setContextCompressionEnabled(e.target.checked)} style={{ width: 18, height: 18, accentColor: "var(--color-info)" }} />
                Enable Context Compression
              </label>
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>When context approaches the threshold, older messages will be automatically summarized to save space</p>
            </div>
            {contextCompressionEnabled && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <label style={{ fontSize: 14, color: "var(--color-text-muted)" }}>Compression Threshold</label>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>{Math.round(contextCompressionThreshold * 100)}%</span>
                </div>
                <input type="range" value={contextCompressionThreshold} onChange={(e) => setContextCompressionThreshold(Number(e.target.value))} min={0.3} max={1} step={0.05} style={{ width: "100%", accentColor: "var(--color-info)" }} />
                <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>Trigger compression when context usage reaches this percentage of the window size</p>
              </div>
            )}
            <div style={{ padding: "12px 14px", borderRadius: 10, background: "var(--color-bg-secondary)", border: "1px solid var(--color-border-default)", fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.6 }}>
              当前会在聊天页实时显示上下文使用率，并按照这里的上限与压缩阈值生效。
            </div>
          </div>
        </section>

        {/* Automation */}
        <section style={{ marginBottom: 40 }}>
          <h2 style={sectionTitle}><Brain size={18} /> Automation</h2>
          <div style={{ border: "1px solid var(--color-border-default)", borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 20, background: "var(--color-bg-card)" }}>
            <div>
              <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--color-text-muted)", cursor: "pointer" }}>
                <input type="checkbox" checked={autoEvolve} onChange={(e) => setAutoEvolve(e.target.checked)} style={{ width: 18, height: 18, accentColor: "var(--color-info)" }} />
                Auto Evolve Skills
              </label>
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>Agent 完成对话后会自动检查失败较多的技能，并在需要时执行 evolve</p>
            </div>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Evolve Threshold</label>
              <input type="number" value={evolveThreshold} onChange={(e) => setEvolveThreshold(Number(e.target.value))} min={1} max={20} style={inputStyle} />
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>当技能失败次数超过该阈值且失败次数大于成功次数时，会触发自动 evolve</p>
            </div>
            <div>
              <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--color-text-muted)", cursor: "pointer" }}>
                <input type="checkbox" checked={memoryAutoCleanupEnabled} onChange={(e) => setMemoryAutoCleanupEnabled(e.target.checked)} style={{ width: 18, height: 18, accentColor: "var(--color-info)" }} />
                Enable Memory Auto Maintenance
              </label>
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>系统会在对话结束后按周期自动清理过旧且价值较低的记忆</p>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
              <div>
                <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Max Age (days)</label>
                <input type="number" value={memoryCleanupMaxAgeDays} onChange={(e) => setMemoryCleanupMaxAgeDays(Number(e.target.value))} min={1} max={365} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Min Importance</label>
                <input type="number" value={memoryCleanupMinImportance} onChange={(e) => setMemoryCleanupMinImportance(Number(e.target.value))} min={0} max={1} step={0.1} style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Interval (hours)</label>
                <input type="number" value={memoryCleanupIntervalHours} onChange={(e) => setMemoryCleanupIntervalHours(Number(e.target.value))} min={1} max={168} style={inputStyle} />
              </div>
            </div>
          </div>
        </section>

        {/* Memory Backend */}
        <section style={{ marginBottom: 40 }}>
          <h2 style={sectionTitle}><Database size={18} /> Memory Backend</h2>
          <div style={{ border: "1px solid var(--color-border-default)", borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", gap: 20, background: "var(--color-bg-card)" }}>
            <div>
              <label style={{ fontSize: 14, color: "var(--color-text-muted)", display: "block", marginBottom: 10 }}>Backend Type</label>
              <div style={{ display: "flex", gap: 10 }}>
                {[
                  { id: "sqlite", name: "SQLite", desc: "关键词匹配，零外部依赖" },
                  { id: "mem0", name: "mem0", desc: "语义向量搜索，需要 Qdrant + Embedding 模型" },
                ].map((b) => (
                  <button key={b.id} onClick={() => setMemoryBackend(b.id)} style={{
                    flex: 1, padding: 14, borderRadius: 10, cursor: "pointer", textAlign: "left",
                    border: memoryBackend === b.id ? "2px solid var(--color-info)" : "1px solid var(--color-border-default)",
                    background: memoryBackend === b.id ? "rgba(59,130,246,0.06)" : "var(--color-bg-elevated)",
                  }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)", marginBottom: 4 }}>{b.name}</div>
                    <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{b.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {memoryBackend === "mem0" && (
              <>
                <div style={{ borderTop: "1px solid var(--color-border-default)", paddingTop: 20 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-secondary)", display: "block", marginBottom: 14 }}>Vector Store (Qdrant)</label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6 }}>Provider</label>
                      <select value={memVectorProvider} onChange={(e) => setMemVectorProvider(e.target.value)} style={inputStyle}>
                        <option value="qdrant">Qdrant</option>
                        <option value="chroma">ChromaDB</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6 }}>Host</label>
                      <input type="text" value={memVectorHost} onChange={(e) => setMemVectorHost(e.target.value)} placeholder="localhost" style={inputStyle} />
                    </div>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6 }}>Port</label>
                      <input type="number" value={memVectorPort} onChange={(e) => setMemVectorPort(Number(e.target.value))} min={1} max={65535} style={inputStyle} />
                    </div>
                  </div>
                </div>

                <div style={{ borderTop: "1px solid var(--color-border-default)", paddingTop: 20 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-secondary)", display: "block", marginBottom: 14 }}>LLM (记忆提取)</label>
                  <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 12 }}>mem0 使用 LLM 从对话中自动提取值得记住的信息</p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6 }}>Provider</label>
                      <select value={memLlmProvider} onChange={(e) => setMemLlmProvider(e.target.value)} style={inputStyle}>
                        {activeProviders.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6 }}>Model</label>
                      <input type="text" value={memLlmModel} onChange={(e) => setMemLlmModel(e.target.value)} placeholder="gpt-4o-mini" style={inputStyle} />
                    </div>
                  </div>
                </div>

                <div style={{ borderTop: "1px solid var(--color-border-default)", paddingTop: 20 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-secondary)", display: "block", marginBottom: 14 }}>Embedding Model (向量嵌入)</label>
                  <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 12 }}>将记忆内容转换为向量，用于语义相似度搜索</p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6 }}>Provider</label>
                      <select value={memEmbedderProvider} onChange={(e) => setMemEmbedderProvider(e.target.value)} style={inputStyle}>
                        {activeProviders.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6 }}>Model</label>
                      <input type="text" value={memEmbedderModel} onChange={(e) => setMemEmbedderModel(e.target.value)} placeholder="text-embedding-3-small" style={inputStyle} />
                    </div>
                  </div>
                </div>

                <div style={{ padding: "12px 14px", borderRadius: 10, background: "rgba(234,179,8,0.06)", border: "1px solid rgba(234,179,8,0.2)", fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.6 }}>
                  ⚠️ 切换到 mem0 后端需要：1) 安装 <code>mem0ai</code> 包 2) 运行 Qdrant 向量数据库 3) 配置有效的 Embedding API Key。保存后需重启服务生效。
                </div>
              </>
            )}
          </div>
        </section>

        {/* Providers */}
        <section style={{ marginBottom: 40 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
            <h2 style={{ ...sectionTitle, marginBottom: 0 }}>Providers</h2>
            <div style={{ position: "relative" }}>
              <button onClick={() => setShowAddMenu(!showAddMenu)} style={{ ...btnSmall, height: 34, padding: "0 14px", fontSize: 13 }}>
                <Plus size={14} /> Add
              </button>
              {showAddMenu && availableToAdd.length > 0 && (
                <div style={{ position: "absolute", top: 40, right: 0, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 10, padding: 6, minWidth: 180, zIndex: 50, boxShadow: "0 8px 32px rgba(0,0,0,0.4)" }}>
                  {availableToAdd.map((p) => (
                    <button key={p.id} onClick={() => addProvider(p.id)} style={{ display: "block", width: "100%", textAlign: "left", padding: "10px 14px", background: "none", border: "none", color: "var(--color-text-primary)", fontSize: 14, cursor: "pointer", borderRadius: 6 }}>
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {loading ? (
            <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)", fontSize: 15 }}>Loading...</div>
          ) : activeProviders.length === 0 ? (
            <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)", fontSize: 15 }}>No providers configured. Click &quot;Add&quot; to add one.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {activeProviders.map((p) => (
                <div key={p.id} style={{ border: "1px solid var(--color-border-default)", borderRadius: 12, padding: 20, background: "var(--color-bg-card)" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <h3 style={{ fontSize: 16, fontWeight: 600 }}>{p.name}</h3>
                      {(defaultProvider === p.id || (!defaultProvider && activeProviders[0]?.id === p.id)) && (
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, fontWeight: 600,
                          color: "var(--color-info)", background: "rgba(59,130,246,0.1)",
                          padding: "2px 8px", borderRadius: 4, border: "1px solid rgba(59,130,246,0.3)"
                        }}>
                          DEFAULT
                        </span>
                      )}
                      {p.is_configured
                        ? <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--color-success)" }}><Check size={13} /> Active</span>
                        : <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--color-text-muted)" }}><AlertTriangle size={13} /> No key</span>}
                    </div>
                    <button onClick={() => removeProvider(p.id)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 4 }}><X size={16} /></button>
                  </div>
                  {p.id !== "ollama" && (
                    <input type="password" value={apiKeys[p.id] || ""} onChange={(e) => setApiKeys((prev) => ({ ...prev, [p.id]: e.target.value }))} placeholder={p.is_configured ? "•••••••• (enter new to change)" : "Enter API Key"} style={{ ...inputStyle, marginBottom: 10, fontSize: 14 }} />
                  )}
                  <input type="text" value={baseUrls[p.id] || ""} onChange={(e) => setBaseUrls((prev) => ({ ...prev, [p.id]: e.target.value }))} placeholder="Base URL (optional, leave empty for default)" style={{ ...inputStyle, marginBottom: 16, fontSize: 13, color: "var(--color-text-muted)" }} />
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Models</span>
                    <button onClick={() => { setShowAddModel(p.id); setNewModelName(""); }} style={btnSmall}>
                      <Plus size={11} /> Add
                    </button>
                  </div>
                  {showAddModel === p.id && (
                    <div style={{ display: "flex", gap: 8, marginBottom: 10, padding: "10px 12px", background: "var(--color-bg-secondary)", borderRadius: 8, border: "1px solid var(--color-border-default)" }}>
                      <input type="text" value={newModelName} onChange={(e) => setNewModelName(e.target.value)} placeholder="Model name (e.g. gpt-4o)" style={{ ...inputStyle, fontSize: 13, padding: "8px 12px", marginBottom: 0, flex: 1 }} onKeyDown={(e) => e.key === "Enter" && handleAddCustomModel(p.id)} />
                      <button onClick={() => handleAddCustomModel(p.id)} style={{ ...btnSmall, background: "var(--color-success)", color: "white", border: "none" }}>Add</button>
                      <button onClick={() => setShowAddModel(null)} style={btnSmall}><X size={11} /></button>
                    </div>
                  )}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {p.models.map((m) => {
                      const isDefaultModel = (defaultProvider === p.id || (!defaultProvider && activeProviders[0]?.id === p.id)) &&
                        (defaultModel === m.id || (!defaultModel && p.models[0]?.id === m.id));
                      return (
                        <span key={m.id} style={{
                          padding: "4px 12px",
                          background: isDefaultModel ? "rgba(59,130,246,0.1)" : "var(--color-bg-elevated)",
                          borderRadius: 6, fontSize: 13,
                          color: isDefaultModel ? "var(--color-info)" : "var(--color-text-muted)",
                          display: "flex", alignItems: "center", gap: 6,
                          border: isDefaultModel ? "1px solid rgba(59,130,246,0.3)" : "1px solid transparent",
                        }}>
                          {m.name}
                          {isDefaultModel && <span style={{ fontSize: 10, fontWeight: 600 }}>★</span>}
                          <button onClick={() => handleRemoveCustomModel(p.id, m.id)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 0, display: "flex" }}><X size={10} /></button>
                        </span>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Save */}
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 14, paddingBottom: 40 }}>
          {saved && <span style={{ fontSize: 14, color: "var(--color-success)", display: "flex", alignItems: "center", gap: 6 }}><Check size={15} /> Saved</span>}
          <button onClick={handleSave} disabled={saving || loading} style={{ padding: "12px 28px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 10, fontSize: 15, fontWeight: 700, cursor: "pointer", opacity: saving ? 0.5 : 1, display: "flex", alignItems: "center", gap: 8 }}>
            <Save size={16} />
            {saving ? "Saving..." : "Save All"}
          </button>
        </div>
      </div>
    </div>
  );
}
