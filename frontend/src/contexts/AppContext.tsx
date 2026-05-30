"use client";

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { fetchProviders, fetchCurrentConfig, fetchAgents } from "@/lib/api";

interface ModelInfo { id: string; name: string; }
interface ProviderInfo { id: string; name: string; models: ModelInfo[]; is_configured: boolean; }
interface AgentInfo { agent_id: string; status: string; current_task?: string; model?: string; provider?: string; parent_agent_id?: string; }

interface AppContextValue {
  // WebSocket agents (real-time)
  wsAgents: AgentInfo[];
  wsConnected: boolean;
  // Cached data
  providers: ProviderInfo[];
  agents: AgentInfo[];
  refreshAgents: () => Promise<void>;
  refreshProviders: () => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const { agents: wsAgents, connected: wsConnected } = useWebSocket();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const providersLoadedRef = useRef(false);

  const refreshProviders = useCallback(async () => {
    try {
      const d = await fetchProviders();
      const all: ProviderInfo[] = d.providers || [];
      let activeIds = all.map((p) => p.id);
      try {
        const cfg = await fetchCurrentConfig();
        if (cfg.active_providers) activeIds = cfg.active_providers;
      } catch {}
      const list = all.filter((p) => activeIds.includes(p.id));
      setProviders(list);
      providersLoadedRef.current = true;
    } catch {}
  }, []);

  const refreshAgents = useCallback(async () => {
    try {
      const d = await fetchAgents();
      setAgents(d.agents || []);
    } catch {}
  }, []);

  // Load providers once
  useEffect(() => {
    if (!providersLoadedRef.current) {
      refreshProviders();
    }
  }, [refreshProviders]);

  // Load agents and poll
  useEffect(() => {
    refreshAgents();
    const interval = setInterval(refreshAgents, 15000);
    return () => clearInterval(interval);
  }, [refreshAgents]);

  return (
    <AppContext.Provider value={{ wsAgents, wsConnected, providers, agents, refreshAgents, refreshProviders }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
