"use client";

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { fetchProviders, fetchCurrentConfig, fetchAgents } from "@/lib/api";

interface ModelInfo { id: string; name: string; }
interface ProviderInfo { id: string; name: string; models: ModelInfo[]; is_configured: boolean; }
interface AgentInfo { agent_id: string; status: string; current_task?: string; model?: string; provider?: string; parent_agent_id?: string; }

// Chat message types
interface ToolCallInfo {
  name: string;
  args: Record<string, unknown>;
  output?: string;
  success?: boolean;
  error?: string;
  status: "calling" | "done" | "error";
  subActivity?: Array<{ type: string; content: string; agent_id: string }>;
}

interface TaskPlanItem {
  id: number;
  description: string;
  status: "pending" | "in_progress" | "completed" | "failed";
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool" | "system" | "error" | "tool_group" | "task_plan";
  content: string;
  toolCalls?: ToolCallInfo[];
  toolResult?: { name: string; success: boolean; output: string };
  agentId?: string;
  timestamp: Date;
  taskPlan?: TaskPlanItem[];
}

interface ContextUsage {
  usage_percent: number;
  estimated_tokens: number;
  context_window: number;
  compression_threshold: number;
}

interface Session {
  session_id: string;
  title: string;
  agent_id?: string;
  model?: string;
  provider?: string;
  message_count?: number;
  last_message_at?: string;
  created_at: string;
}

interface AppContextValue {
  // WebSocket agents (real-time)
  wsAgents: AgentInfo[];
  wsConnected: boolean;
  // WebSocket event subscription (agent_created, agent_deleted)
  onAgentEvent: (callback: (event: string, data: unknown) => void) => () => void;
  // Cached data
  providers: ProviderInfo[];
  agents: AgentInfo[];
  providerVersion: number;
  refreshAgents: () => Promise<void>;
  refreshProviders: () => Promise<void>;
  // Chat state (persists across page navigation)
  chatMessages: ChatMessage[];
  setChatMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  chatSessionId: string;
  setChatSessionId: (id: string) => void;
  chatProvider: string;
  setChatProvider: (p: string) => void;
  chatModel: string;
  setChatModel: (m: string) => void;
  chatAgentFilter: string;
  setChatAgentFilter: (f: string) => void;
  chatContextUsage: ContextUsage | null;
  setChatContextUsage: React.Dispatch<React.SetStateAction<ContextUsage | null>>;
  chatSessions: Session[];
  setChatSessions: React.Dispatch<React.SetStateAction<Session[]>>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const { agents: wsAgents, connected: wsConnected, onAgentEvent } = useWebSocket();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [providerVersion, setProviderVersion] = useState(0);
  const providersLoadedRef = useRef(false);

  // Chat state - persists across page navigation
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatSessionId, setChatSessionIdState] = useState(() => {
    if (typeof window !== "undefined") {
      return sessionStorage.getItem("kevin_session_id") || crypto.randomUUID();
    }
    return crypto.randomUUID();
  });
  const [chatProvider, setChatProvider] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [chatAgentFilter, setChatAgentFilter] = useState("all");
  const [chatContextUsage, setChatContextUsage] = useState<ContextUsage | null>(null);
  const [chatSessions, setChatSessions] = useState<Session[]>([]);

  const setChatSessionId = useCallback((id: string) => {
    setChatSessionIdState(id);
    if (typeof window !== "undefined") {
      sessionStorage.setItem("kevin_session_id", id);
    }
  }, []);

  const refreshProviders = useCallback(async () => {
    try {
      // Fetch providers and current config in parallel
      const [providersData, configData] = await Promise.all([
        fetchProviders(),
        fetchCurrentConfig().catch(() => null),
      ]);
      const all: ProviderInfo[] = providersData.providers || [];
      const activeIds: string[] = configData?.active_providers || all.map((p) => p.id);
      const list = all.filter((p) => activeIds.includes(p.id));
      setProviders(list);
      setProviderVersion((v) => v + 1);
      providersLoadedRef.current = true;

      // Initialize chatProvider and chatModel from current config if they're empty
      if (configData) {
        setChatProvider((prev) => {
          if (!prev && configData.provider) return configData.provider;
          return prev;
        });
        setChatModel((prev) => {
          if (!prev && configData.model) return configData.model;
          return prev;
        });
      }
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
    <AppContext.Provider value={{
      wsAgents, wsConnected, onAgentEvent, providers, agents, providerVersion, refreshAgents, refreshProviders,
      chatMessages, setChatMessages, chatSessionId, setChatSessionId,
      chatProvider, setChatProvider, chatModel, setChatModel,
      chatAgentFilter, setChatAgentFilter, chatContextUsage, setChatContextUsage,
      chatSessions, setChatSessions,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

export type { ChatMessage, ToolCallInfo, TaskPlanItem, ContextUsage, Session, AppContextValue };
