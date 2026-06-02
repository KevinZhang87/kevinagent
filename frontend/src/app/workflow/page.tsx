"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Position,
  Handle,
  Panel,
  type NodeProps,
  type OnConnect,
  type Connection,
  addEdge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { fetchWorkflow, createAgent, deleteAgent, updateAgent } from "@/lib/api";
import { useApp } from "@/contexts/AppContext";
import { Bot, Cpu, Zap, RefreshCw, Plus, Trash2, Activity, X, Settings } from "lucide-react";

const statusColors: Record<string, string> = {
  idle: "var(--color-border-hover)",
  thinking: "var(--color-info)",
  executing: "var(--color-warning)",
  error: "var(--color-error)",
  cancelled: "var(--color-text-muted)",
};

const statusGlows: Record<string, string> = {
  idle: "none",
  thinking: "0 0 8px rgba(59,130,246,0.25)",
  executing: "0 0 8px rgba(245,158,11,0.25)",
  error: "0 0 8px rgba(239,68,68,0.25)",
  cancelled: "none",
};

const statusLabels: Record<string, string> = {
  idle: "Idle",
  thinking: "Thinking...",
  executing: "Executing",
  error: "Error",
  cancelled: "Cancelled",
};

const AVAILABLE_TOOLS = [
  { id: "shell", name: "Shell", desc: "Execute shell commands" },
  { id: "python_exec", name: "Python", desc: "Execute Python code" },
  { id: "file_read", name: "Read Files", desc: "Read file contents" },
  { id: "file_write", name: "Write Files", desc: "Create/modify files" },
  { id: "web_search", name: "Web Search", desc: "Search the internet" },
  { id: "memory_save", name: "Memory", desc: "Save to long-term memory" },
  { id: "call_agent", name: "Call Agent", desc: "Delegate to sub-agents" },
  { id: "create_agent", name: "Create Agent", desc: "Create new agents" },
  { id: "list_agents", name: "List Agents", desc: "List available agents" },
  { id: "shared_read", name: "Shared Read", desc: "Read shared files" },
  { id: "shared_write", name: "Shared Write", desc: "Write shared files" },
  { id: "shared_list", name: "Shared List", desc: "List shared files" },
];

interface AgentNodeData {
  label: string;
  status: string;
  model?: string;
  provider?: string;
  current_task?: string;
  agent_id: string;
  parent_agent_id?: string;
  ephemeral?: boolean;
  [key: string]: unknown;
}

function AgentNode({ data }: NodeProps) {
  const d = data as AgentNodeData;
  const status = d.status || "idle";

  return (
    <div
      style={{
        background: "var(--color-bg-card)",
        border: `1.5px ${d.ephemeral ? "dashed" : "solid"} ${statusColors[status] || "var(--color-border-default)"}`,
        borderRadius: 8,
        padding: "8px 12px",
        width: "fit-content",
        maxWidth: 200,
        boxShadow: `0 4px 16px rgba(0,0,0,0.3), ${statusGlows[status] || "none"}`,
        transition: "box-shadow 0.3s, border-color 0.3s",
        position: "relative",
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "var(--color-bg-elevated)", width: 6, height: 6, border: "1.5px solid var(--color-border-hover)" }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "var(--color-bg-elevated)", width: 6, height: 6, border: "1.5px solid var(--color-border-hover)" }}
      />

      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: d.model ? 4 : 0 }}>
        <div
          style={{
            width: 18, height: 18, borderRadius: 4,
            background: "var(--color-bg-elevated)",
            border: "1px solid var(--color-border-default)",
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {d.agent_id === "main" ? <Bot size={9} color="var(--color-text-secondary)" /> : <Cpu size={9} color="var(--color-text-secondary)" />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.label}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 3, marginTop: 1 }}>
            <span style={{ width: 4, height: 4, borderRadius: "50%", background: statusColors[status] || "var(--color-text-muted)", flexShrink: 0 }} />
            <span style={{ fontSize: 9, color: "var(--color-text-muted)" }}>{statusLabels[status] || status}</span>
          </div>
        </div>
      </div>

      {d.model && (
        <div style={{ display: "flex", alignItems: "center", gap: 3, paddingLeft: 24 }}>
          <Zap size={8} color="var(--color-text-muted)" />
          <span style={{ fontSize: 9, color: "var(--color-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.provider} / {d.model}</span>
        </div>
      )}
      {d.ephemeral && (
        <span style={{
          position: "absolute", top: -6, right: -6,
          fontSize: 8, fontWeight: 700, color: "var(--color-warning)",
          background: "var(--color-bg-card)", border: "1px solid var(--color-warning)",
          borderRadius: 4, padding: "1px 4px", lineHeight: "12px",
        }}>临时</span>
      )}
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

interface AgentInfo {
  agent_id: string; status: string; current_task?: string;
  model?: string; provider?: string; parent_agent_id?: string;
  ephemeral?: boolean;
}

type FlowNode = Node<AgentNodeData>;
type FlowEdge = Edge;

const inputStyle: React.CSSProperties = {
  width: "100%",
  background: "var(--color-bg-elevated)",
  border: "1px solid var(--color-border-default)",
  borderRadius: 8,
  padding: "10px 14px",
  fontSize: 14,
  color: "var(--color-text-primary)",
  outline: "none",
  transition: "border-color 0.15s",
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "var(--color-text-muted)",
  display: "block",
  marginBottom: 4,
  fontWeight: 500,
};

function WorkflowPageContent() {
  const { wsAgents, onAgentEvent, providers, agents: agentList, refreshAgents } = useApp();
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);
  const [loading, setLoading] = useState(false);
  const [showCreateAgent, setShowCreateAgent] = useState(false);
  const [showEditAgent, setShowEditAgent] = useState(false);
  const [newAgent, setNewAgent] = useState({ name: "", provider: "", model: "", parent_agent_id: "main", description: "", system_prompt: "", capabilities: [] as string[], tools: [] as string[] });
  const [editAgent, setEditAgent] = useState({ agent_id: "", provider: "", model: "", parent_agent_id: "", description: "", system_prompt: "", capabilities: [] as string[], tools: [] as string[] });
  const [newCapInput, setNewCapInput] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  const [selectedAgentDetail, setSelectedAgentDetail] = useState<{ description?: string; system_prompt?: string; capabilities?: string[]; tools?: string[] } | null>(null);
  const [editError, setEditError] = useState("");
  const [cancelMsg, setCancelMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  // Track agent activity log (status changes with timestamps)
  const [agentActivity, setAgentActivity] = useState<Record<string, Array<{ time: Date; status: string; task: string }>>>({});

  // Update activity log when wsAgents changes
  useEffect(() => {
    setAgentActivity((prev) => {
      const updated = { ...prev };
      for (const agent of wsAgents) {
        const lastEntry = updated[agent.agent_id]?.[updated[agent.agent_id]?.length - 1];
        // Only add entry if status or task changed
        if (!lastEntry || lastEntry.status !== agent.status || lastEntry.task !== (agent.current_task || "")) {
          const entries = updated[agent.agent_id] || [];
          entries.push({ time: new Date(), status: agent.status, task: agent.current_task || "" });
          // Keep last 20 entries per agent
          updated[agent.agent_id] = entries.slice(-20);
        }
      }
      return updated;
    });
  }, [wsAgents]);

  // Load extended agent details when selectedAgent changes
  useEffect(() => {
    if (!selectedAgent) { setSelectedAgentDetail(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const { fetchAgentDetail } = await import("@/lib/api");
        const detail = await fetchAgentDetail(selectedAgent.agent_id);
        if (!cancelled) setSelectedAgentDetail(detail);
      } catch { if (!cancelled) setSelectedAgentDetail(null); }
    })();
    return () => { cancelled = true; };
  }, [selectedAgent?.agent_id]);

  // Handle agent_created and agent_deleted WebSocket events
  useEffect(() => {
    const unsubscribe = onAgentEvent((event, data) => {
      if (event === "agent_created") {
        const agent = data as { agent_id: string; status: string; model: string; provider: string; parent_agent_id: string | null; ephemeral: boolean };
        // Auto-add new node to the graph
        setNodes((prev) => {
          if (prev.some((n) => n.id === agent.agent_id)) return prev;
          // Position below parent node
          const parentNode = agent.parent_agent_id ? prev.find((n) => n.id === agent.parent_agent_id) : null;
          const baseX = parentNode ? parentNode.position.x : 250 * (prev.length % 3);
          const baseY = parentNode ? parentNode.position.y + 120 : 150 * Math.floor(prev.length / 3);
          // Offset horizontally to avoid overlap
          const siblings = prev.filter((n) => (n.data as AgentNodeData)?.parent_agent_id === agent.parent_agent_id);
          const offsetX = siblings.length * 220;
          const newNode: FlowNode = {
            id: agent.agent_id,
            type: "agent",
            position: { x: baseX + offsetX, y: baseY },
            data: {
              label: agent.agent_id.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()),
              status: agent.status,
              model: agent.model,
              provider: agent.provider,
              agent_id: agent.agent_id,
              parent_agent_id: agent.parent_agent_id || undefined,
              ephemeral: agent.ephemeral,
            },
          };
          return [...prev, newNode];
        });
        // Auto-add edge from parent
        if (agent.parent_agent_id) {
          setEdges((prev) => {
            const edgeId = `${agent.parent_agent_id}-${agent.agent_id}`;
            if (prev.some((e) => e.id === edgeId)) return prev;
            const newEdge: FlowEdge = {
              id: edgeId,
              source: agent.parent_agent_id!,
              target: agent.agent_id,
              animated: agent.status !== "idle",
              style: { stroke: "var(--color-border-hover)", strokeWidth: 1.5 },
            };
            return [...prev, newEdge];
          });
        }
        refreshAgents();
      } else if (event === "agent_deleted") {
        const deleted = data as { agent_id: string };
        // Remove node and connected edges
        setNodes((prev) => prev.filter((n) => n.id !== deleted.agent_id));
        setEdges((prev) => prev.filter((e) => e.source !== deleted.agent_id && e.target !== deleted.agent_id));
        if (selectedAgent?.agent_id === deleted.agent_id) {
          setSelectedAgent(null);
        }
        refreshAgents();
      }
    });
    return unsubscribe;
  }, [onAgentEvent, setNodes, setEdges, selectedAgent, refreshAgents]);

  const loadWorkflow = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchWorkflow();
      const flowNodes: FlowNode[] = (data.agents || []).map(
        (a: { id: string; name: string; status: string; model?: string; provider?: string; current_task?: string; parent_agent_id?: string; ephemeral?: boolean; position?: { x: number; y: number } }) => ({
          id: a.id,
          type: "agent" as const,
          position: a.position || { x: 0, y: 0 },
          data: { label: a.name, status: a.status, model: a.model || "", provider: a.provider || "", current_task: a.current_task, agent_id: a.id, parent_agent_id: a.parent_agent_id, ephemeral: a.ephemeral || false },
        })
      );

      // Build edges from parent_agent_id relationships
      const flowEdges: FlowEdge[] = [];
      for (const node of flowNodes) {
        const parentId = node.data.parent_agent_id;
        if (parentId && parentId !== node.id) {
          flowEdges.push({
            id: `${parentId}-${node.id}`,
            source: parentId,
            target: node.id,
            animated: node.data.status !== "idle",
            style: { stroke: "var(--color-border-hover)", strokeWidth: 1.5 },
          });
        }
      }

      if (flowNodes.length === 0) {
        flowNodes.push({
          id: "main",
          type: "agent",
          position: { x: 300, y: 100 },
          data: { label: "Main Agent", status: "idle", model: "", provider: "", agent_id: "main" },
        });
      }

      setNodes(flowNodes);
      setEdges(flowEdges);
    } catch (e) {
      console.error("Failed to load workflow:", e);
    } finally { setLoading(false); }
  }, [setNodes, setEdges]);

  const loadAgents = useCallback(async () => {
    await refreshAgents();
  }, [refreshAgents]);

  const loadProviders = useCallback(async () => {
    // Providers are already loaded from AppContext, just init newAgent defaults
    if (providers.length > 0) {
      setNewAgent((prev) => {
        if (prev.provider) return prev;
        const first = providers[0];
        const firstModel = first.models[0]?.id || "";
        return { ...prev, provider: first.id, model: firstModel };
      });
    }
  }, [providers]);

  useEffect(() => { loadWorkflow(); loadAgents(); loadProviders(); }, [loadWorkflow, loadAgents, loadProviders]);

  // Update nodes from WebSocket agent state
  useEffect(() => {
    if (wsAgents.length > 0) {
      setNodes((nds) =>
        nds.map((n) => {
          const agentState = wsAgents.find((a) => a.agent_id === n.id);
          if (agentState) {
            return { ...n, data: { ...n.data, status: agentState.status, current_task: agentState.current_task, model: agentState.model || n.data.model, provider: agentState.provider || n.data.provider } };
          }
          return n;
        })
      );
      // Sync selectedAgent too
      if (selectedAgent) {
        const ws = wsAgents.find((x) => x.agent_id === selectedAgent.agent_id);
        if (ws) {
          setSelectedAgent((prev) => prev ? { ...prev, status: ws.status, current_task: ws.current_task, model: ws.model || prev.model, provider: ws.provider || prev.provider } : prev);
        }
      }
    }
  }, [wsAgents, setNodes]);

  const onConnect: OnConnect = useCallback(async (connection: Connection) => {
    setEdges((eds) => addEdge({ ...connection, animated: true, style: { stroke: "var(--color-border-hover)", strokeWidth: 1.5 } }, eds));
    // Persist the connection: target's parent = source
    if (connection.source && connection.target) {
      try {
        await updateAgent(connection.target, { parent_agent_id: connection.source });
      } catch (e) {
        console.error("Failed to persist edge:", e);
      }
    }
  }, [setEdges]);

  const handleCreateAgent = async () => {
    if (!newAgent.name.trim()) return;
    try {
      await createAgent({
        name: newAgent.name, provider: newAgent.provider, model: newAgent.model, parent_agent_id: newAgent.parent_agent_id,
        description: newAgent.description || undefined,
        system_prompt: newAgent.system_prompt || undefined,
        capabilities: newAgent.capabilities.length > 0 ? newAgent.capabilities : undefined,
        tools: newAgent.tools.length > 0 ? newAgent.tools : undefined,
      });
      setShowCreateAgent(false);
      const firstProvider = providers[0];
      setNewAgent({ name: "", provider: firstProvider?.id || "", model: firstProvider?.models[0]?.id || "", parent_agent_id: "main", description: "", system_prompt: "", capabilities: [], tools: [] });
      await loadWorkflow();
      await loadAgents();
    } catch {}
  };

  const handleDeleteAgent = async (agentId: string) => {
    try {
      const result = await deleteAgent(agentId);
      if (result.detail) {
        console.error("Delete agent failed:", result.detail);
        return;
      }
      if (selectedAgent?.agent_id === agentId) setSelectedAgent(null);
      await loadWorkflow();
      await loadAgents();
    } catch (e) {
      console.error("Delete agent error:", e);
    }
  };

  const handleEditAgent = async (agent: AgentInfo) => {
    const currentProvider = agent.provider || providers[0]?.id || "openai";
    const p = providers.find((x) => x.id === currentProvider);
    const currentModel = agent.model || p?.models[0]?.id || "";
    // Load full agent details from API
    let description = "", system_prompt = "", capabilities: string[] = [], tools: string[] = [];
    try {
      const { fetchAgentDetail } = await import("@/lib/api");
      const detail = await fetchAgentDetail(agent.agent_id);
      description = detail.description || "";
      system_prompt = detail.system_prompt || "";
      capabilities = detail.capabilities || [];
      tools = detail.tools || [];
    } catch {}
    setEditAgent({ agent_id: agent.agent_id, provider: currentProvider, model: currentModel, parent_agent_id: agent.parent_agent_id || "main", description, system_prompt, capabilities, tools });
    setEditError("");
    setShowEditAgent(true);
  };

  const handleSaveEditAgent = async () => {
    try {
      setEditError("");
      await updateAgent(editAgent.agent_id, {
        provider: editAgent.provider, model: editAgent.model, parent_agent_id: editAgent.parent_agent_id,
        description: editAgent.description || undefined,
        system_prompt: editAgent.system_prompt || undefined,
        capabilities: editAgent.capabilities.length > 0 ? editAgent.capabilities : undefined,
        tools: editAgent.tools.length > 0 ? editAgent.tools : undefined,
      });
      setShowEditAgent(false);
      await loadWorkflow();
      await loadAgents();
      if (selectedAgent?.agent_id === editAgent.agent_id) {
        setSelectedAgent({ ...selectedAgent, provider: editAgent.provider, model: editAgent.model, parent_agent_id: editAgent.parent_agent_id });
      }
    } catch (e) {
      setEditError(e instanceof Error ? e.message : "Failed to update agent");
    }
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <header style={{ height: 56, borderBottom: "1px solid var(--color-border-default)", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, background: "var(--color-bg-elevated)" }}>
        <span style={{ fontSize: 14, fontWeight: 600 }}>Workflow</span>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => setShowCreateAgent(true)} style={{ display: "flex", alignItems: "center", gap: 5, height: 30, padding: "0 12px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
            <Plus size={12} /> New Agent
          </button>
          <button onClick={loadWorkflow} disabled={loading} style={{ display: "flex", alignItems: "center", gap: 5, height: 30, padding: "0 12px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>
            <RefreshCw size={12} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
          </button>
        </div>
      </header>

      <div style={{ flex: 1, position: "relative" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => {
            const agent = agentList.find((a) => a.agent_id === node.data.agent_id);
            if (agent) setSelectedAgent(agent);
          }}
          onPaneClick={() => setSelectedAgent(null)}
          nodeTypes={nodeTypes}
          fitView
          style={{ background: "var(--color-bg-primary)" }}
          defaultEdgeOptions={{ style: { stroke: "var(--color-border-hover)", strokeWidth: 1.5 } }}
          minZoom={0.3}
          maxZoom={2}
        >
          <Background color="rgba(255,255,255,0.03)" gap={24} size={1} />
          <Controls showInteractive={false} style={{ borderRadius: 8, overflow: "hidden" }} />
          <MiniMap nodeColor="var(--color-bg-elevated)" maskColor="rgba(0,0,0,0.6)" style={{ width: 120, height: 80, borderRadius: 8, overflow: "hidden" }} />

          {/* Agent List Panel */}
          <Panel position="top-right" style={{ background: "var(--color-bg-card)", borderRadius: 10, border: "1px solid var(--color-border-default)", padding: 12, minWidth: 220, maxWidth: 260, maxHeight: 440, overflowY: "auto", boxShadow: "0 4px 20px rgba(0,0,0,0.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
              <Activity size={12} color="var(--color-text-muted)" />
              <span style={{ fontSize: 12, fontWeight: 600 }}>Agents</span>
              <span style={{ fontSize: 10, color: "var(--color-text-muted)", marginLeft: "auto", background: "var(--color-bg-secondary)", padding: "1px 6px", borderRadius: 4 }}>{agentList.length}</span>
            </div>
            {agentList.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", textAlign: "center", padding: "12px 0" }}>No agents yet</p>
            ) : agentList.map((a) => (
              <div key={a.agent_id} onClick={() => setSelectedAgent(a)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 9px", borderRadius: 6, marginBottom: 3, background: selectedAgent?.agent_id === a.agent_id ? "var(--color-bg-elevated)" : "transparent", border: `1px solid ${selectedAgent?.agent_id === a.agent_id ? "var(--color-border-hover)" : "transparent"}`, cursor: "pointer", transition: "background 0.15s, border-color 0.15s" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusColors[a.status] || "var(--color-text-muted)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {a.agent_id === "main" ? "Main Agent" : a.agent_id}
                  </div>
                </div>
                <button onClick={(e) => { e.stopPropagation(); handleEditAgent(a); }} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 2, opacity: 0.4 }} onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")} onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.4")} title="Edit">
                  <Settings size={11} />
                </button>
                {a.agent_id !== "main" && (
                  <button onClick={(e) => { e.stopPropagation(); handleDeleteAgent(a.agent_id); }} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 2, opacity: 0.4 }} onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")} onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.4")}>
                    <Trash2 size={11} />
                  </button>
                )}
              </div>
            ))}

            {/* Cancel feedback toast */}
            {cancelMsg && (
              <div style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8, fontSize: 12, fontWeight: 500, background: cancelMsg.type === "success" ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)", border: `1px solid ${cancelMsg.type === "success" ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`, color: cancelMsg.type === "success" ? "var(--color-success)" : "var(--color-error)" }}>
                {cancelMsg.text}
              </div>
            )}

            {/* Agent Detail */}
            {selectedAgent && (
              <div style={{ marginTop: 8, padding: 10, background: "var(--color-bg-secondary)", borderRadius: 8, border: `1px solid ${selectedAgent.status !== "idle" ? statusColors[selectedAgent.status] : "var(--color-border-default)"}`, transition: "border-color 0.3s" }}>
                {/* Header */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 22, height: 22, borderRadius: 6, background: selectedAgent.status !== "idle" ? `${statusColors[selectedAgent.status]}20` : "var(--color-bg-elevated)", display: "flex", alignItems: "center", justifyContent: "center", transition: "background 0.3s" }}>
                      {selectedAgent.agent_id === "main" ? <Bot size={11} color={statusColors[selectedAgent.status]} /> : <Cpu size={11} color={statusColors[selectedAgent.status]} />}
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{selectedAgent.agent_id === "main" ? "Main Agent" : selectedAgent.agent_id}</span>
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    {(selectedAgent.status === "thinking" || selectedAgent.status === "executing") && (
                      <button onClick={async () => {
                        try {
                          const { cancelAgent } = await import("@/lib/api");
                          const res = await cancelAgent(selectedAgent.agent_id);
                          setCancelMsg({ type: "success", text: res.message || "Cancel requested" });
                          setTimeout(() => setCancelMsg(null), 3000);
                          await refreshAgents();
                        } catch (e: any) {
                          setCancelMsg({ type: "error", text: e?.message || "Cancel failed" });
                          setTimeout(() => setCancelMsg(null), 3000);
                        }
                      }} style={{ background: "none", border: "1px solid var(--color-error)", borderRadius: 5, padding: "2px 6px", cursor: "pointer", color: "var(--color-error)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                        <X size={10} /> Cancel
                      </button>
                    )}
                    <button onClick={() => handleEditAgent(selectedAgent)} style={{ background: "none", border: "1px solid var(--color-border-default)", borderRadius: 5, padding: "2px 6px", cursor: "pointer", color: "var(--color-text-secondary)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                      <Settings size={10} /> Edit
                    </button>
                  </div>
                </div>

                {/* Status with animated indicator */}
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6, padding: "6px 8px", background: selectedAgent.status !== "idle" ? `${statusColors[selectedAgent.status]}10` : "var(--color-bg-elevated)", borderRadius: 6, transition: "background 0.3s" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: statusColors[selectedAgent.status] || "var(--color-text-muted)", boxShadow: selectedAgent.status !== "idle" ? `0 0 8px ${statusColors[selectedAgent.status]}` : "none", animation: selectedAgent.status === "thinking" ? "pulse 1.5s infinite" : "none" }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: statusColors[selectedAgent.status] || "var(--color-text-muted)" }}>{statusLabels[selectedAgent.status] || selectedAgent.status}</span>
                </div>

                {/* Current Task - Full display when executing */}
                {selectedAgent.current_task && (
                  <div style={{ marginBottom: 6, padding: "6px 8px", background: "var(--color-bg-elevated)", borderRadius: 6, border: "1px solid var(--color-border-default)" }}>
                    <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginBottom: 3, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Current Task</div>
                    <p style={{ margin: 0, fontSize: 11, color: "var(--color-text-secondary)", lineHeight: 1.5, wordBreak: "break-word" }}>{selectedAgent.current_task}</p>
                  </div>
                )}

                {/* Basic Info */}
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", display: "flex", flexDirection: "column", gap: 3 }}>
                  {selectedAgent.parent_agent_id && (
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span>Parent</span>
                      <span style={{ color: "var(--color-text-secondary)", fontWeight: 500 }}>{selectedAgent.parent_agent_id === "main" ? "Main Agent" : selectedAgent.parent_agent_id}</span>
                    </div>
                  )}
                  <div>
                    <span style={{ display: "block", marginBottom: 3 }}>Provider / Model</span>
                    <div style={{ display: "flex", gap: 4 }}>
                      <select
                        value={selectedAgent.provider || providers[0]?.id || ""}
                        onChange={async (e) => {
                          const newProvider = e.target.value;
                          const p = providers.find((x) => x.id === newProvider);
                          const newModel = p?.models[0]?.id || "";
                          try {
                            await updateAgent(selectedAgent.agent_id, { provider: newProvider, model: newModel });
                            setSelectedAgent({ ...selectedAgent, provider: newProvider, model: newModel });
                            await loadWorkflow();
                            await loadAgents();
                          } catch {}
                        }}
                        style={{ flex: 1, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 4, padding: "3px 6px", fontSize: 11, color: "var(--color-text-primary)", outline: "none" }}
                      >
                        {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                      <select
                        value={selectedAgent.model || ""}
                        onChange={async (e) => {
                          const newModel = e.target.value;
                          try {
                            await updateAgent(selectedAgent.agent_id, { provider: selectedAgent.provider, model: newModel });
                            setSelectedAgent({ ...selectedAgent, model: newModel });
                            await loadWorkflow();
                            await loadAgents();
                          } catch {}
                        }}
                        style={{ flex: 1, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 4, padding: "3px 6px", fontSize: 11, color: "var(--color-text-primary)", outline: "none" }}
                      >
                        {(providers.find((p) => p.id === (selectedAgent.provider || providers[0]?.id))?.models || []).map((m) => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Extended Info */}
                {selectedAgentDetail && (
                  <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-text-muted)", display: "flex", flexDirection: "column", gap: 6 }}>
                    {selectedAgentDetail.description && (
                      <div style={{ padding: "6px 8px", background: "var(--color-bg-elevated)", borderRadius: 6 }}>
                        <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 3 }}>Description</div>
                        <p style={{ margin: 0, fontSize: 11, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>{selectedAgentDetail.description}</p>
                      </div>
                    )}
                    {selectedAgentDetail.capabilities && selectedAgentDetail.capabilities.length > 0 && (
                      <div style={{ padding: "6px 8px", background: "var(--color-bg-elevated)", borderRadius: 6 }}>
                        <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>Capabilities</div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {selectedAgentDetail.capabilities.map((cap, i) => (
                            <span key={i} style={{ padding: "2px 6px", background: "var(--color-bg-secondary)", border: "1px solid var(--color-border-default)", borderRadius: 3, fontSize: 10, color: "var(--color-text-secondary)" }}>{cap}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {selectedAgentDetail.tools && selectedAgentDetail.tools.length > 0 && (
                      <div style={{ padding: "6px 8px", background: "var(--color-bg-elevated)", borderRadius: 6 }}>
                        <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>Tools</div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {selectedAgentDetail.tools.map((tool, i) => (
                            <span key={i} style={{ padding: "2px 6px", background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.2)", borderRadius: 3, fontSize: 10, color: "var(--color-info)" }}>{tool}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {selectedAgentDetail.system_prompt && (
                      <details style={{ padding: "6px 8px", background: "var(--color-bg-elevated)", borderRadius: 6 }}>
                        <summary style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, cursor: "pointer", color: "var(--color-text-muted)" }}>System Prompt</summary>
                        <p style={{ margin: "6px 0 0", fontSize: 10, color: "var(--color-text-secondary)", lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{selectedAgentDetail.system_prompt}</p>
                      </details>
                    )}
                  </div>
                )}

                {/* Activity Log */}
                {agentActivity[selectedAgent.agent_id] && agentActivity[selectedAgent.agent_id].length > 0 && (
                  <div style={{ marginTop: 6, padding: "6px 8px", background: "var(--color-bg-elevated)", borderRadius: 6, border: "1px solid var(--color-border-default)" }}>
                    <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Activity Log</div>
                    <div style={{ maxHeight: 120, overflowY: "auto" }}>
                      {agentActivity[selectedAgent.agent_id].slice(-8).reverse().map((entry, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 6, padding: "3px 0", borderBottom: i < 7 ? "1px solid var(--color-border-default)" : "none" }}>
                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: statusColors[entry.status] || "var(--color-text-muted)", flexShrink: 0, marginTop: 4 }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: 10, color: statusColors[entry.status] || "var(--color-text-muted)", fontWeight: 500 }}>{statusLabels[entry.status] || entry.status}</span>
                              <span style={{ fontSize: 9, color: "var(--color-text-muted)", opacity: 0.6 }}>{entry.time.toLocaleTimeString()}</span>
                            </div>
                            {entry.task && <div style={{ fontSize: 9, color: "var(--color-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.task}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Panel>

          {/* Help hint */}
          <Panel position="bottom-left" style={{ background: "var(--color-bg-card)", borderRadius: 8, border: "1px solid var(--color-border-default)", padding: "6px 10px", fontSize: 11, color: "var(--color-text-muted)" }}>
            Drag to arrange &middot; Connect handles to link agents
          </Panel>
        </ReactFlow>

        {/* ===== Create Agent Dialog ===== */}
        {showCreateAgent && (
          <>
            <div onClick={() => setShowCreateAgent(false)} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 99, backdropFilter: "blur(2px)" }} />
            <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 12, padding: "18px 20px", width: 420, maxHeight: "85vh", overflowY: "auto", boxShadow: "0 12px 40px rgba(0,0,0,0.5)", zIndex: 100 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>New Agent</h3>
                <button onClick={() => setShowCreateAgent(false)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 2 }}><X size={14} /></button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div>
                  <label style={labelStyle}>Name</label>
                  <input type="text" value={newAgent.name} onChange={(e) => setNewAgent((p) => ({ ...p, name: e.target.value }))} placeholder="e.g. Researcher" style={inputStyle} autoFocus />
                </div>
                <div>
                  <label style={labelStyle}>Description</label>
                  <input type="text" value={newAgent.description} onChange={(e) => setNewAgent((p) => ({ ...p, description: e.target.value }))} placeholder="e.g. Research specialist for web gathering" style={inputStyle} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div>
                    <label style={labelStyle}>Provider</label>
                    <select value={newAgent.provider} onChange={(e) => {
                      const pid = e.target.value;
                      const p = providers.find((x) => x.id === pid);
                      setNewAgent((prev) => ({ ...prev, provider: pid, model: p?.models[0]?.id || "" }));
                    }} style={inputStyle}>
                      {providers.map((p) => <option key={p.id} value={p.id}>{p.name}{p.is_configured ? "" : " (no key)"}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Model</label>
                    {(() => {
                      const currentProvider = providers.find((p) => p.id === newAgent.provider);
                      const modelList = currentProvider?.models || [];
                      return modelList.length > 0 ? (
                        <select value={newAgent.model} onChange={(e) => setNewAgent((prev) => ({ ...prev, model: e.target.value }))} style={inputStyle}>
                          {modelList.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                        </select>
                      ) : (
                        <input type="text" value={newAgent.model} onChange={(e) => setNewAgent((prev) => ({ ...prev, model: e.target.value }))} placeholder="e.g. gpt-4o" style={inputStyle} />
                      );
                    })()}
                  </div>
                </div>
                <div>
                  <label style={labelStyle}>Parent Agent</label>
                  <select value={newAgent.parent_agent_id} onChange={(e) => setNewAgent((prev) => ({ ...prev, parent_agent_id: e.target.value }))} style={inputStyle}>
                    {agentList.map((a) => (
                      <option key={a.agent_id} value={a.agent_id}>{a.agent_id === "main" ? "Main Agent" : a.agent_id}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>System Prompt</label>
                  <textarea value={newAgent.system_prompt} onChange={(e) => setNewAgent((p) => ({ ...p, system_prompt: e.target.value }))} placeholder="Define the agent's role, personality, and behavior constraints..." rows={3} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit", minHeight: 60 }} />
                </div>
                <div>
                  <label style={labelStyle}>Capabilities</label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: newAgent.capabilities.length > 0 ? 6 : 0 }}>
                    {newAgent.capabilities.map((cap, i) => (
                      <span key={i} style={{ display: "flex", alignItems: "center", gap: 3, padding: "2px 8px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 4, fontSize: 11, color: "var(--color-text-secondary)" }}>
                        {cap}
                        <button onClick={() => setNewAgent((p) => ({ ...p, capabilities: p.capabilities.filter((_, j) => j !== i) }))} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, color: "var(--color-text-muted)", display: "flex" }}><X size={10} /></button>
                      </span>
                    ))}
                  </div>
                  <input type="text" value={newCapInput} onChange={(e) => setNewCapInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && newCapInput.trim()) { setNewAgent((p) => ({ ...p, capabilities: [...p.capabilities, newCapInput.trim()] })); setNewCapInput(""); } }} placeholder="Type capability and press Enter" style={{ ...inputStyle, fontSize: 12 }} />
                </div>
                <div>
                  <label style={labelStyle}>Tool Whitelist <span style={{ fontWeight: 400, color: "var(--color-text-muted)" }}>(empty = all tools)</span></label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {AVAILABLE_TOOLS.map((t) => {
                      const selected = newAgent.tools.includes(t.id);
                      return (
                        <button key={t.id} onClick={() => setNewAgent((p) => ({ ...p, tools: selected ? p.tools.filter((x) => x !== t.id) : [...p.tools, t.id] }))} title={t.desc} style={{
                          padding: "3px 8px", borderRadius: 4, fontSize: 10, cursor: "pointer",
                          border: selected ? "1px solid var(--color-info)" : "1px solid var(--color-border-default)",
                          background: selected ? "rgba(59,130,246,0.1)" : "var(--color-bg-elevated)",
                          color: selected ? "var(--color-info)" : "var(--color-text-muted)",
                          fontWeight: selected ? 600 : 400,
                        }}>{t.name}</button>
                      );
                    })}
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, marginTop: 4 }}>
                  <button onClick={() => setShowCreateAgent(false)} style={{ padding: "6px 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>Cancel</button>
                  <button onClick={handleCreateAgent} disabled={!newAgent.name.trim()} style={{ padding: "6px 14px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer", opacity: !newAgent.name.trim() ? 0.4 : 1 }}>Create</button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ===== Edit Agent Dialog ===== */}
        {showEditAgent && (
          <>
            <div onClick={() => setShowEditAgent(false)} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 99, backdropFilter: "blur(2px)" }} />
            <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 12, padding: "18px 20px", width: 420, maxHeight: "85vh", overflowY: "auto", boxShadow: "0 12px 40px rgba(0,0,0,0.5)", zIndex: 100 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Edit: {editAgent.agent_id === "main" ? "Main Agent" : editAgent.agent_id}</h3>
                <button onClick={() => setShowEditAgent(false)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 2 }}><X size={14} /></button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div>
                  <label style={labelStyle}>Description</label>
                  <input type="text" value={editAgent.description} onChange={(e) => setEditAgent((p) => ({ ...p, description: e.target.value }))} placeholder="Agent's role description" style={inputStyle} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div>
                    <label style={labelStyle}>Provider</label>
                    <select value={editAgent.provider} onChange={(e) => {
                      const pid = e.target.value;
                      const p = providers.find((x) => x.id === pid);
                      setEditAgent((prev) => ({ ...prev, provider: pid, model: p?.models[0]?.id || "" }));
                    }} style={inputStyle}>
                      {providers.map((p) => <option key={p.id} value={p.id}>{p.name}{p.is_configured ? "" : " (no key)"}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Model</label>
                    {(() => {
                      const currentProvider = providers.find((p) => p.id === editAgent.provider);
                      const modelList = currentProvider?.models || [];
                      return modelList.length > 0 ? (
                        <select value={editAgent.model} onChange={(e) => setEditAgent((prev) => ({ ...prev, model: e.target.value }))} style={inputStyle}>
                          {modelList.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                        </select>
                      ) : (
                        <input type="text" value={editAgent.model} onChange={(e) => setEditAgent((prev) => ({ ...prev, model: e.target.value }))} placeholder="e.g. gpt-4o" style={inputStyle} />
                      );
                    })()}
                  </div>
                </div>
                {editAgent.agent_id !== "main" && (
                  <div>
                    <label style={labelStyle}>Parent Agent</label>
                    <select value={editAgent.parent_agent_id} onChange={(e) => setEditAgent((prev) => ({ ...prev, parent_agent_id: e.target.value }))} style={inputStyle}>
                      {agentList.filter((a) => a.agent_id !== editAgent.agent_id).map((a) => (
                        <option key={a.agent_id} value={a.agent_id}>{a.agent_id === "main" ? "Main Agent" : a.agent_id}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div>
                  <label style={labelStyle}>System Prompt</label>
                  <textarea value={editAgent.system_prompt} onChange={(e) => setEditAgent((p) => ({ ...p, system_prompt: e.target.value }))} placeholder="Define the agent's role, personality, and behavior constraints..." rows={3} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit", minHeight: 60 }} />
                </div>
                <div>
                  <label style={labelStyle}>Capabilities</label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: editAgent.capabilities.length > 0 ? 6 : 0 }}>
                    {editAgent.capabilities.map((cap, i) => (
                      <span key={i} style={{ display: "flex", alignItems: "center", gap: 3, padding: "2px 8px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 4, fontSize: 11, color: "var(--color-text-secondary)" }}>
                        {cap}
                        <button onClick={() => setEditAgent((p) => ({ ...p, capabilities: p.capabilities.filter((_, j) => j !== i) }))} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, color: "var(--color-text-muted)", display: "flex" }}><X size={10} /></button>
                      </span>
                    ))}
                  </div>
                  <input type="text" value={newCapInput} onChange={(e) => setNewCapInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && newCapInput.trim()) { setEditAgent((p) => ({ ...p, capabilities: [...p.capabilities, newCapInput.trim()] })); setNewCapInput(""); } }} placeholder="Type capability and press Enter" style={{ ...inputStyle, fontSize: 12 }} />
                </div>
                <div>
                  <label style={labelStyle}>Tool Whitelist <span style={{ fontWeight: 400, color: "var(--color-text-muted)" }}>(empty = all tools)</span></label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {AVAILABLE_TOOLS.map((t) => {
                      const selected = editAgent.tools.includes(t.id);
                      return (
                        <button key={t.id} onClick={() => setEditAgent((p) => ({ ...p, tools: selected ? p.tools.filter((x) => x !== t.id) : [...p.tools, t.id] }))} title={t.desc} style={{
                          padding: "3px 8px", borderRadius: 4, fontSize: 10, cursor: "pointer",
                          border: selected ? "1px solid var(--color-info)" : "1px solid var(--color-border-default)",
                          background: selected ? "rgba(59,130,246,0.1)" : "var(--color-bg-elevated)",
                          color: selected ? "var(--color-info)" : "var(--color-text-muted)",
                          fontWeight: selected ? 600 : 400,
                        }}>{t.name}</button>
                      );
                    })}
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, marginTop: 4 }}>
                  {editError && <span style={{ fontSize: 11, color: "var(--color-error)", marginRight: "auto", alignSelf: "center" }}>{editError}</span>}
                  <button onClick={() => setShowEditAgent(false)} style={{ padding: "6px 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>Cancel</button>
                  <button onClick={handleSaveEditAgent} style={{ padding: "6px 14px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Save</button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function WorkflowPage() {
  return <WorkflowPageContent />;
}
