"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createWebSocket } from "@/lib/api";

interface AgentState {
  agent_id: string;
  status: string;
  current_task?: string;
  model?: string;
  provider?: string;
  parent_agent_id?: string;
  ephemeral?: boolean;
}

export interface AgentCreatedEvent {
  agent_id: string;
  status: string;
  model: string;
  provider: string;
  parent_agent_id: string | null;
  ephemeral: boolean;
}

export interface AgentDeletedEvent {
  agent_id: string;
}

type WSEventCallback = (event: string, data: AgentCreatedEvent | AgentDeletedEvent) => void;

const MAX_RETRIES = 10;
const BASE_DELAY = 1000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [connected, setConnected] = useState(false);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const eventCallbacksRef = useRef<WSEventCallback[]>([]);

  const onAgentEvent = useCallback((callback: WSEventCallback) => {
    eventCallbacksRef.current.push(callback);
    return () => {
      eventCallbacksRef.current = eventCallbacksRef.current.filter((cb) => cb !== callback);
    };
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = createWebSocket();
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnected(true);
      retryCountRef.current = 0;
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(event.data);
        if (data.type === "init") {
          setAgents(data.agents || []);
        } else if (data.type === "agent_update") {
          setAgents((prev) => {
            const idx = prev.findIndex((a) => a.agent_id === data.agent_id);
            const update: AgentState = {
              agent_id: data.agent_id,
              status: data.status,
              current_task: data.current_task,
              model: data.model,
              provider: data.provider,
            };
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = { ...updated[idx], ...update };
              return updated;
            }
            return [...prev, update];
          });
        } else if (data.type === "agent_created") {
          const agentData = data.agent as AgentCreatedEvent;
          setAgents((prev) => {
            if (prev.some((a) => a.agent_id === agentData.agent_id)) return prev;
            return [...prev, {
              agent_id: agentData.agent_id,
              status: agentData.status,
              model: agentData.model,
              provider: agentData.provider,
              parent_agent_id: agentData.parent_agent_id || undefined,
              ephemeral: agentData.ephemeral,
            }];
          });
          eventCallbacksRef.current.forEach((cb) => cb("agent_created", agentData));
        } else if (data.type === "agent_deleted") {
          const deletedData = data as AgentDeletedEvent;
          setAgents((prev) => prev.filter((a) => a.agent_id !== deletedData.agent_id));
          eventCallbacksRef.current.forEach((cb) => cb("agent_deleted", deletedData));
        }
      } catch {}
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnected(false);
      if (retryCountRef.current < MAX_RETRIES) {
        const delay = Math.min(BASE_DELAY * Math.pow(2, retryCountRef.current), 30000);
        retryCountRef.current += 1;
        retryTimerRef.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { agents, connected, onAgentEvent };
}
