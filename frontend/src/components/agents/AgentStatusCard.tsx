"use client";

import { memo } from "react";
import { Bot, Cpu } from "lucide-react";

interface AgentState {
  agent_id: string;
  status: string;
  current_task?: string;
  model?: string;
  provider?: string;
}

const statusColors: Record<string, string> = {
  idle: "var(--color-text-muted)",
  thinking: "var(--color-info)",
  executing: "var(--color-warning)",
  error: "var(--color-error)",
};

export const AgentStatusCard = memo(function AgentStatusCard({ agent }: { agent: AgentState }) {
  return (
    <div style={{ padding: "12px 14px", borderRadius: 10, marginBottom: 6, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: "var(--color-bg-elevated)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {agent.agent_id === "main" ? <Bot size={15} color="var(--color-text-muted)" /> : <Cpu size={15} color="var(--color-text-muted)" />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {agent.agent_id === "main" ? "Main Agent" : agent.agent_id}
            </span>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: statusColors[agent.status] || "var(--color-text-muted)", flexShrink: 0, boxShadow: agent.status !== "idle" ? `0 0 8px ${statusColors[agent.status]}` : "none" }} />
          </div>
          {agent.current_task && <p style={{ fontSize: 13, color: "var(--color-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 4 }}>{agent.current_task}</p>}
        </div>
      </div>
    </div>
  );
});
