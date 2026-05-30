"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createWebSocket } from "@/lib/api";

interface AgentState {
  agent_id: string;
  status: string;
  current_task?: string;
  model?: string;
  provider?: string;
}

const MAX_RETRIES = 10;
const BASE_DELAY = 1000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [connected, setConnected] = useState(false);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = createWebSocket();
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnected(true);
      retryCountRef.current = 0; // Reset retry count on successful connect
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
        }
      } catch {}
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnected(false);
      // Exponential backoff with max retries
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

  return { agents, connected };
}
