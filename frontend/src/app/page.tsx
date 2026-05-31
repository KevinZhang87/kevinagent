"use client";

import { useState, useRef, useEffect, useCallback, useMemo, memo } from "react";
import { ChatMessage, TypingIndicator } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { useApp } from "@/contexts/AppContext";
import type { ChatMessage as ChatMessageType, Session } from "@/contexts/AppContext";
import { streamChat, streamChatWithFiles, fetchSessions, fetchSessionMessages, deleteSession, evolveSkills } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";
import type { AttachedFile } from "@/components/chat/ChatInput";
import { Bot, Plus, Trash2, MessageSquare, ChevronLeft, ChevronRight, Brain, RefreshCw, Users, AlertTriangle } from "lucide-react";
import Link from "next/link";

type Message = ChatMessageType;

const selectStyle: React.CSSProperties = {
  height: 36, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
  borderRadius: 8, padding: "0 30px 0 12px", fontSize: 14, color: "var(--color-text-secondary)",
  outline: "none", cursor: "pointer", appearance: "none", WebkitAppearance: "none",
  backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'10\' height=\'10\' fill=\'%23888\' viewBox=\'0 0 16 16\'%3E%3Cpath d=\'M8 11L3 6h10z\'/%3E%3C/svg%3E")',
  backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center",
};

// Memoized message item to avoid re-rendering unchanged messages
const MessageItem = memo(function MessageItem({ msg }: { msg: Message }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <ChatMessage message={msg} />
    </div>
  );
});

// Memoized session item
const SessionItem = memo(function SessionItem({
  s, isActive, onClick, onDelete,
}: {
  s: Session; isActive: boolean;
  onClick: () => void; onDelete: (e: React.MouseEvent) => void;
}) {
  // Format time display
  const timeStr = formatRelativeTime(s.updated_at || s.created_at);

  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", borderRadius: 8,
        cursor: "pointer", marginBottom: 2, fontSize: 13,
        background: isActive ? "var(--color-bg-elevated)" : "transparent",
        color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
        border: "none", width: "100%", textAlign: "left",
        transition: "background 0.15s",
      }}
    >
      <MessageSquare size={14} style={{ flexShrink: 0, opacity: 0.5 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {s.title}
        </div>
        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2, opacity: 0.7 }}>{timeStr}</div>
      </div>
      <button
        onClick={onDelete}
        style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 2, opacity: 0.4, flexShrink: 0 }}
        onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
        onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.4")}
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
});

function ChatPageContent() {
  const {
    wsAgents, providers, agents: agentList, providerVersion, refreshProviders,
    chatMessages, setChatMessages, chatSessionId, setChatSessionId,
    chatProvider, setChatProvider, chatModel, setChatModel,
    chatAgentFilter, setChatAgentFilter, chatContextUsage, setChatContextUsage,
    chatSessions, setChatSessions,
  } = useApp();
  const [messages, setMessages] = [chatMessages, setChatMessages] as const;
  const [isLoading, setIsLoading] = useState(false);
  const sessionId = chatSessionId;
  const setSessionId = setChatSessionId;
  const provider = chatProvider;
  const setProvider = setChatProvider;
  const model = chatModel;
  const setModel = setChatModel;
  const sessions = chatSessions;
  const setSessions = setChatSessions;
  const [showHistory, setShowHistory] = useState(true);
  const [agentId, setAgentId] = useState("main");
  const agentFilter = chatAgentFilter;
  const setAgentFilter = setChatAgentFilter;
  const contextUsage = chatContextUsage;
  const setContextUsage = setChatContextUsage;
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [evolving, setEvolving] = useState(false);
  const [evolveResult, setEvolveResult] = useState("");
  const [showAgentsDrawer, setShowAgentsDrawer] = useState(false);
  const agentsDrawerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-restore messages when returning to the page with a saved session
  // Only fetch if messages are empty (context was cleared or first load)
  const hasRestoredRef = useRef(false);
  useEffect(() => {
    if (hasRestoredRef.current) return;
    if (messages.length > 0) {
      hasRestoredRef.current = true;
      return;
    }
    const saved = sessionId;
    if (saved) {
      hasRestoredRef.current = true;
      fetchSessionMessages(saved).then((d) => {
        const rawMsgs = d.messages || [];
        if (rawMsgs.length === 0) return;
        const loadedMsgs: Message[] = [];
        let pendingToolGroup: Message | null = null;
        for (const m of rawMsgs) {
          const msgId = String(m.id);
          const role = m.role;
          const msgAgentId = m.agent_id || "main";
          const isChildAgent = msgAgentId !== "main";

          // Skip child agent's user messages (they are task prompts, not real user input)
          if (isChildAgent && role === "user") continue;

          if (role === "tool") {
            // Tool result: find matching tool call in pending group and update to "done"
            if (pendingToolGroup && pendingToolGroup.toolCalls) {
              let matched = false;
              for (let i = 0; i < pendingToolGroup.toolCalls.length; i++) {
                if (pendingToolGroup.toolCalls[i].status === "calling") {
                  pendingToolGroup.toolCalls[i] = {
                    ...pendingToolGroup.toolCalls[i],
                    output: m.content,
                    success: true,
                    status: "done" as const,
                  };
                  matched = true;
                  break;
                }
              }
              if (!matched) {
                pendingToolGroup.toolCalls!.push({ name: "tool", args: {}, output: m.content, success: true, status: "done" as const });
              }
            }
          } else if (role === "assistant" && m.tool_calls) {
            // Assistant with tool calls: flush previous, create new tool_group
            if (pendingToolGroup) { loadedMsgs.push(pendingToolGroup); pendingToolGroup = null; }
            let parsedToolCalls;
            try { parsedToolCalls = JSON.parse(m.tool_calls); } catch { parsedToolCalls = null; }
            const toolCallsArray = Array.isArray(parsedToolCalls) ? parsedToolCalls : (parsedToolCalls ? [parsedToolCalls] : []);
            if (toolCallsArray.length > 0) {
              pendingToolGroup = {
                id: msgId + "_tg",
                role: "tool_group" as const,
                content: "",
                toolCalls: toolCallsArray.map((tc: { name?: string; arguments?: string }) => ({
                  name: tc.name || "tool",
                  args: tc.arguments ? (() => { try { return JSON.parse(tc.arguments); } catch { return {}; } })() : {},
                  status: "calling" as const,
                })),
                agentId: msgAgentId,
                timestamp: new Date(m.created_at),
              };
            }
            // Only push assistant message if it has text content
            if (m.content && m.content.trim()) {
              loadedMsgs.push({ id: msgId, role: "assistant" as const, content: m.content, agentId: msgAgentId, timestamp: new Date(m.created_at) });
            }
          } else {
            if (pendingToolGroup) { loadedMsgs.push(pendingToolGroup); pendingToolGroup = null; }
            loadedMsgs.push({ id: msgId, role: role as Message["role"], content: m.content, agentId: msgAgentId, timestamp: new Date(m.created_at) });
          }
        }
        if (pendingToolGroup) loadedMsgs.push(pendingToolGroup);
        setMessages(loadedMsgs);
      }).catch(() => {});
    }
  }, []);

  // Throttled auto-scroll: only scroll when near bottom, use requestAnimationFrame
  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    });
  }, []);

  // Initialize provider/model from shared context, re-initialize when providerVersion changes
  const lastProviderVersion = useRef(0);
  const modelPerProvider = useRef<Record<string, string>>({});
  useEffect(() => {
    // Only re-initialize when providerVersion actually changes (not on initial mount with empty providers)
    if (providerVersion === 0) return;
    if (lastProviderVersion.current === providerVersion) return;
    lastProviderVersion.current = providerVersion;

    if (providers.length > 0) {
      // Try to find a configured provider, fall back to first available
      const configured = providers.find((p) => p.is_configured) || providers[0];
      if (configured) {
        // Only switch if current provider is no longer in the list
        if (!providers.some((p) => p.id === provider)) {
          setProvider(configured.id);
          if (configured.models.length > 0) setModel(configured.models[0].id);
        } else if (provider && !currentProvider?.models.some((m) => m.id === model)) {
          // Provider still exists but current model is gone, switch to first model
          const p = providers.find((p) => p.id === provider);
          if (p && p.models.length > 0) setModel(p.models[0].id);
        }
      }
    }
  }, [providerVersion, providers]);

  // Refresh providers when page becomes visible (e.g. after returning from Settings)
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        refreshProviders();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [refreshProviders]);

  // Load sessions
  const loadSessions = useCallback(async () => {
    try {
      const d = await fetchSessions();
      setSessions(d.sessions || []);
    } catch {}
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // Update model when provider changes: restore remembered model or fall back to first model
  useEffect(() => {
    const p = providers.find((p) => p.id === provider);
    if (!p || p.models.length === 0) return;

    // Check if we have a remembered model for this provider
    const remembered = modelPerProvider.current[provider];
    if (remembered && p.models.some((m) => m.id === remembered)) {
      if (model !== remembered) setModel(remembered);
    } else if (!p.models.some((m) => m.id === model)) {
      // Current model not in this provider's list, fall back to first
      setModel(p.models[0].id);
    }
  }, [provider, providers, model]);

  // Persist model selection per provider
  const handleProviderChange = useCallback((newProvider: string) => {
    if (provider && model) {
      modelPerProvider.current[provider] = model;
    }
    setProvider(newProvider);
  }, [provider, model, setProvider]);

  const handleModelChange = useCallback((newModel: string) => {
    setModel(newModel);
    if (provider) {
      modelPerProvider.current[provider] = newModel;
    }
  }, [provider, setModel]);

  // Auto-scroll only when messages length changes (new message added), not on content updates
  const msgCount = messages.length;
  useEffect(() => { scrollToBottom(); }, [msgCount, scrollToBottom]);

  const currentProvider = providers.find((p) => p.id === provider);

  // Switch to a session
  const switchSession = useCallback(async (s: Session) => {
    setSessionId(s.session_id);
    setAgentFilter("all");
    try {
      const d = await fetchSessionMessages(s.session_id);
      const rawMsgs = d.messages || [];
      const loadedMsgs: Message[] = [];
      let pendingToolGroup: Message | null = null;

      for (const m of rawMsgs) {
        const msgId = String(m.id);
        const role = m.role;
        const msgAgentId = m.agent_id || "main";
        const isChildAgent = msgAgentId !== "main";

        // Skip child agent's user messages (they are task prompts, not real user input)
        if (isChildAgent && role === "user") continue;

        if (role === "tool") {
          // Tool result: find matching tool call in pending group and update it to "done"
          if (pendingToolGroup && pendingToolGroup.toolCalls) {
            const toolCallId = m.tool_call_id || "";
            let matched = false;
            for (let i = 0; i < pendingToolGroup.toolCalls.length; i++) {
              if (pendingToolGroup.toolCalls[i].status === "calling") {
                pendingToolGroup.toolCalls[i] = {
                  ...pendingToolGroup.toolCalls[i],
                  output: m.content,
                  success: true,
                  status: "done" as const,
                };
                matched = true;
                break;
              }
            }
            if (!matched) {
              // Fallback: add as generic tool result
              pendingToolGroup.toolCalls!.push({
                name: "tool",
                args: {},
                output: m.content,
                success: true,
                status: "done" as const,
              });
            }
          }
        } else if (role === "assistant" && m.tool_calls) {
          // Assistant with tool calls: flush previous group, create new tool_group
          if (pendingToolGroup) {
            loadedMsgs.push(pendingToolGroup);
            pendingToolGroup = null;
          }
          let parsedToolCalls;
          try { parsedToolCalls = JSON.parse(m.tool_calls); } catch { parsedToolCalls = null; }
          // Handle both single tool call and array of tool calls
          const toolCallsArray = Array.isArray(parsedToolCalls) ? parsedToolCalls : (parsedToolCalls ? [parsedToolCalls] : []);
          if (toolCallsArray.length > 0) {
            pendingToolGroup = {
              id: msgId + "_tg",
              role: "tool_group" as const,
              content: "",
              toolCalls: toolCallsArray.map((tc: { name?: string; arguments?: string }) => ({
                name: tc.name || "tool",
                args: tc.arguments ? (() => { try { return JSON.parse(tc.arguments); } catch { return {}; } })() : {},
                status: "calling" as const,
              })),
              agentId: msgAgentId,
              timestamp: new Date(m.created_at),
            };
          }
          // Only push assistant message if it has text content (not just tool calls)
          if (m.content && m.content.trim()) {
            loadedMsgs.push({
              id: msgId,
              role: "assistant" as const,
              content: m.content,
              agentId: msgAgentId,
              timestamp: new Date(m.created_at),
            });
          }
        } else {
          if (pendingToolGroup) {
            loadedMsgs.push(pendingToolGroup);
            pendingToolGroup = null;
          }
          loadedMsgs.push({
            id: msgId,
            role: role as Message["role"],
            content: m.content,
            agentId: msgAgentId,
            timestamp: new Date(m.created_at),
          });
        }
      }
      if (pendingToolGroup) {
        loadedMsgs.push(pendingToolGroup);
      }
      setMessages(loadedMsgs);
    } catch {
      setMessages([]);
    }
  }, []);

  // Create new chat
  const newChat = useCallback(async () => {
    const newId = crypto.randomUUID();
    setSessionId(newId);
    setMessages([]);
    setAgentFilter("all");
  }, []);

  // Delete session
  const handleDeleteSession = useCallback(async (e: React.MouseEvent, s: Session) => {
    e.stopPropagation();
    try {
      await deleteSession(s.session_id);
      if (s.session_id === sessionId) {
        newChat();
      }
      loadSessions();
    } catch {}
  }, [sessionId, newChat, loadSessions]);

  // Evolve skills
  const handleEvolve = async () => {
    setEvolving(true);
    setEvolveResult("");
    try {
      const d = await evolveSkills();
      const count = d.evolved?.length || 0;
      setEvolveResult(count > 0 ? `${count} skill(s) evolved` : "No skills needed evolution");
      setTimeout(() => setEvolveResult(""), 3000);
    } catch {
      setEvolveResult("Evolution failed");
      setTimeout(() => setEvolveResult(""), 3000);
    } finally {
      setEvolving(false);
    }
  };

  const handleSend = useCallback(async (content: string, files?: AttachedFile[]) => {
    // Build display content including file names
    const fileNames = files?.map((f) => f.file.name).join(", ") || "";
    const displayContent = content || (fileNames ? `Sent: ${fileNames}` : "");
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: displayContent, agentId, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    // Use ref to accumulate streaming text to avoid excessive state updates
    let currentAssistant = "";
    let pendingUpdate: Message | null = null;
    let updateTimer: ReturnType<typeof setTimeout> | null = null;

    // Batched update: flush accumulated text changes at ~60fps
    const flushUpdate = () => {
      if (pendingUpdate) {
        const msg = pendingUpdate;
        pendingUpdate = null;
        setMessages((prev) => {
          const f = prev.filter((m) => m.id !== "streaming");
          return [...f, msg];
        });
      }
      updateTimer = null;
    };

    const scheduleUpdate = (msg: Message) => {
      pendingUpdate = msg;
      if (!updateTimer) {
        updateTimer = setTimeout(flushUpdate, 16); // ~60fps
      }
    };

    try {
      // Choose the right API based on whether files are attached
      const chatStream = files && files.length > 0
        ? streamChatWithFiles(content, sessionId, provider, model, files.map((f) => f.file), agentId)
        : streamChat(content, sessionId, provider, model, agentId);

      for await (const chunk of chatStream) {
        const chunkAgentId = chunk.agent_id || agentId;
        if (chunk.type === "text") {
          currentAssistant += chunk.content;
          scheduleUpdate({ id: "streaming", role: "assistant" as const, content: currentAssistant, agentId: chunkAgentId, timestamp: new Date() });
        } else if (chunk.type === "tool_call") {
          // Flush any pending text first
          if (updateTimer) { clearTimeout(updateTimer); flushUpdate(); }
          try {
            const tc = JSON.parse(chunk.content);
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === "tool_group") {
                return [...prev.slice(0, -1), {
                  ...last,
                  toolCalls: [...(last.toolCalls || []), { name: tc.name, args: tc.args, status: "calling" }],
                }];
              }
              return [...prev, { id: crypto.randomUUID(), role: "tool_group" as const, content: "", toolCalls: [{ name: tc.name, args: tc.args, status: "calling" }], agentId: chunkAgentId, timestamp: new Date() }];
            });
            // Mark next pending task as in_progress when call_agent starts
            if (tc.name === "call_agent") {
              setMessages((prev) => {
                for (let i = prev.length - 1; i >= 0; i--) {
                  if (prev[i].role === "task_plan" && prev[i].taskPlan) {
                    const plan = [...(prev[i].taskPlan || [])];
                    for (let j = 0; j < plan.length; j++) {
                      if (plan[j].status === "pending") {
                        plan[j] = { ...plan[j], status: "in_progress" };
                        break;
                      }
                    }
                    const newPrev = [...prev];
                    newPrev[i] = { ...newPrev[i], taskPlan: plan };
                    return newPrev;
                  }
                }
                return prev;
              });
            }
          } catch {}
        } else if (chunk.type === "tool_result") {
          if (updateTimer) { clearTimeout(updateTimer); flushUpdate(); }
          try {
            const r = JSON.parse(chunk.content);
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === "tool_group") {
                const tools = [...(last.toolCalls || [])];
                for (let i = tools.length - 1; i >= 0; i--) {
                  if (tools[i].status === "calling") {
                    tools[i] = {
                      ...tools[i],
                      status: r.success ? "done" : "error",
                      output: r.output,
                      error: r.error,
                      success: r.success,
                    };
                    break;
                  }
                }
                return [...prev.slice(0, -1), { ...last, toolCalls: tools }];
              }
              return prev;
            });
          } catch {}
        } else if (chunk.type === "sub_agent_activity") {
          // Forward sub-agent progress to the call_agent tool's subActivity array
          try {
            const activity = JSON.parse(chunk.content);
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === "tool_group") {
                const tools = [...(last.toolCalls || [])];
                // Find the last call_agent tool that's still calling
                for (let i = tools.length - 1; i >= 0; i--) {
                  if (tools[i].name === "call_agent" && tools[i].status === "calling") {
                    tools[i] = {
                      ...tools[i],
                      subActivity: [...(tools[i].subActivity || []), activity],
                    };
                    break;
                  }
                }
                return [...prev.slice(0, -1), { ...last, toolCalls: tools }];
              }
              return prev;
            });
          } catch {}
        } else if (chunk.type === "task_plan") {
          // Task plan from main agent - create a task_plan message
          if (updateTimer) { clearTimeout(updateTimer); flushUpdate(); }
          try {
            const plan = JSON.parse(chunk.content);
            setMessages((prev) => [...prev, {
              id: crypto.randomUUID(),
              role: "task_plan" as const,
              content: "",
              taskPlan: plan.tasks,
              agentId: chunkAgentId,
              timestamp: new Date(),
            }]);
          } catch {}
        } else if (chunk.type === "task_plan_update") {
          // Update task plan status when call_agent completes
          try {
            const update = JSON.parse(chunk.content);
            setMessages((prev) => {
              // Find the last task_plan message and update matching task
              for (let i = prev.length - 1; i >= 0; i--) {
                if (prev[i].role === "task_plan" && prev[i].taskPlan) {
                  const plan = [...(prev[i].taskPlan || [])];
                  // Match by agent_id in the task description or find next pending task
                  let updated = false;
                  for (let j = 0; j < plan.length; j++) {
                    if (plan[j].status === "in_progress") {
                      plan[j] = { ...plan[j], status: update.success ? "completed" : "failed" };
                      updated = true;
                      break;
                    }
                  }
                  // If no in_progress found, mark next pending as completed
                  if (!updated) {
                    for (let j = 0; j < plan.length; j++) {
                      if (plan[j].status === "pending") {
                        plan[j] = { ...plan[j], status: update.success ? "completed" : "failed" };
                        break;
                      }
                    }
                  }
                  const newPrev = [...prev];
                  newPrev[i] = { ...newPrev[i], taskPlan: plan };
                  return newPrev;
                }
              }
              return prev;
            });
          } catch {}
        } else if (chunk.type === "status") {
          try {
            setContextUsage(JSON.parse(chunk.content));
          } catch {}
        } else if (chunk.type === "error") {
          if (updateTimer) { clearTimeout(updateTimer); flushUpdate(); }
          setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "error" as const, content: chunk.content, agentId: chunkAgentId, timestamp: new Date() }]);
        }
      }
      // Final flush
      if (updateTimer) { clearTimeout(updateTimer); flushUpdate(); }
      if (currentAssistant) setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, id: crypto.randomUUID() } : m)));
      loadSessions();
    } catch (e) {
      if (updateTimer) { clearTimeout(updateTimer); flushUpdate(); }
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "error" as const, content: `Connection error: ${e instanceof Error ? e.message : "Unknown"}`, timestamp: new Date() }]);
    } finally { setIsLoading(false); }
  }, [sessionId, provider, model, agentId, loadSessions]);

  // Memoize session items to avoid re-rendering all sessions on every change
  const sessionItems = useMemo(() => sessions, [sessions]);

  // Compute unique agent IDs in current conversation for filtering
  const agentIdsInChat = useMemo(() => {
    const ids = new Set<string>();
    for (const m of messages) {
      if (m.agentId) ids.add(m.agentId);
    }
    return Array.from(ids).sort((a, b) => (a === "main" ? -1 : b === "main" ? 1 : a.localeCompare(b)));
  }, [messages]);

  // Filter messages by selected agent
  const filteredMessages = useMemo(() => {
    if (agentFilter === "all") return messages;
    return messages.filter((m) => {
      const mAgentId = m.agentId || "main";
      return mAgentId === agentFilter;
    });
  }, [messages, agentFilter]);

  return (
    <div style={{ display: "flex", height: "100%", position: "relative" }}>
      {/* Session History Sidebar */}
      {showHistory && (
        <div style={{ width: 240, borderRight: "1px solid var(--color-border-default)", background: "var(--color-bg-secondary)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 1 }}>History</span>
            <button onClick={newChat} style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 28, height: 28, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, cursor: "pointer", color: "var(--color-text-secondary)" }}>
              <Plus size={14} />
            </button>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "8px 8px" }}>
            {sessionItems.length === 0 ? (
              <div style={{ textAlign: "center", padding: "32px 16px", color: "var(--color-text-muted)", fontSize: 13 }}>
                No chat history yet
              </div>
            ) : sessionItems.map((s) => (
              <SessionItem
                key={s.session_id}
                s={s}
                isActive={s.session_id === sessionId}
                onClick={() => switchSession(s)}
                onDelete={(e) => handleDeleteSession(e, s)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header style={{ minHeight: 56, borderBottom: "1px solid var(--color-border-default)", padding: "8px 24px", display: "flex", alignItems: "center", flexShrink: 0, flexWrap: "wrap", gap: 8, background: "var(--color-bg-elevated)", overflow: "visible" }}>
          <button onClick={() => setShowHistory(!showHistory)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 4, marginRight: 12, display: "flex", alignItems: "center" }}>
            {showHistory ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
          </button>
          <span style={{ fontSize: 17, fontWeight: 700 }}>Chat</span>
          {agentIdsInChat.length > 1 && (
            <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)} style={{ ...selectStyle, marginLeft: 10, minWidth: 100 }}>
              <option value="all">All Agents</option>
              {agentIdsInChat.map((id) => (
                <option key={id} value={id}>{id === "main" ? "Main Agent" : id}</option>
              ))}
            </select>
          )}
          {contextUsage && (
            <div title={`Context: ${contextUsage.estimated_tokens.toLocaleString()} / ${contextUsage.context_window.toLocaleString()} tokens (${contextUsage.usage_percent}%)`} style={{ marginLeft: 8, display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", border: "1px solid var(--color-border-default)", borderRadius: 8, background: "var(--color-bg-secondary)", fontSize: 12, color: "var(--color-text-muted)" }}>
              <Brain size={13} color={contextUsage.usage_percent >= contextUsage.compression_threshold * 100 ? "var(--color-warning)" : "var(--color-info)"} />
              <span>{contextUsage.usage_percent}%</span>
            </div>
          )}
          <div style={{ display: "flex", gap: 10, marginLeft: "auto" }}>
            <select value={agentId} onChange={(e) => setAgentId(e.target.value)} style={selectStyle}>
              <option value="main">Main Agent</option>
              {agentList.filter((a) => a.agent_id !== "main").map((a) => (
                <option key={a.agent_id} value={a.agent_id}>{a.agent_id}</option>
              ))}
            </select>
            {providers.length === 0 ? (
              <span style={{ fontSize: 13, color: "var(--color-warning)", display: "flex", alignItems: "center", gap: 6 }}>
                <AlertTriangle size={14} />
                No providers configured —
                <Link href="/settings" style={{ color: "var(--color-info)", textDecoration: "underline" }}>Go to Settings</Link>
              </span>
            ) : (
              <>
                <select value={provider} onChange={(e) => handleProviderChange(e.target.value)} style={selectStyle}>
                  {providers.map((p) => <option key={p.id} value={p.id}>{p.name}{p.is_configured ? "" : " (no key)"}</option>)}
                </select>
                <select
                  value={model}
                  onChange={(e) => handleModelChange(e.target.value)}
                  style={selectStyle}
                  disabled={!currentProvider || currentProvider.models.length === 0}
                  title={!currentProvider ? "Select a provider first" : currentProvider.models.length === 0 ? "No models configured for this provider" : "Select model"}
                >
                  {!currentProvider || currentProvider.models.length === 0 ? (
                    <option value="">{!currentProvider ? "Select a provider" : "No models"}</option>
                  ) : (
                    currentProvider.models.map((m) => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))
                  )}
                </select>
              </>
            )}
            <button
              onClick={handleEvolve}
              disabled={evolving}
              style={{
                display: "flex", alignItems: "center", gap: 6, height: 36, padding: "0 14px",
                background: evolving ? "var(--color-bg-hover)" : "var(--color-bg-elevated)",
                border: "1px solid var(--color-border-default)", borderRadius: 8,
                fontSize: 13, color: evolving ? "var(--color-text-muted)" : "var(--color-warning)",
                cursor: evolving ? "wait" : "pointer",
              }}
              title="Evolve skills based on recent conversations"
            >
              <RefreshCw size={14} style={{ animation: evolving ? "spin 1s linear infinite" : "none" }} />
              Evolve
            </button>
          </div>
        </header>
        {evolveResult && (
          <div style={{
            padding: "6px 20px", background: evolveResult.includes("failed") ? "rgba(239,68,68,0.08)" : "rgba(34,197,94,0.08)",
            borderBottom: `1px solid ${evolveResult.includes("failed") ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)"}`,
            fontSize: 12, color: evolveResult.includes("failed") ? "var(--color-error)" : "var(--color-success)", textAlign: "center",
          }}>
            {evolveResult}
          </div>
        )}

        <div ref={scrollContainerRef} style={{ flex: 1, overflowY: "auto", background: "var(--color-bg-primary)" }}>
          {messages.length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", padding: 24 }}>
              <div style={{ width: 64, height: 64, borderRadius: 18, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 28 }}>
                <Bot size={28} color="var(--color-text-muted)" />
              </div>
              <h2 style={{ fontSize: 26, fontWeight: 700, marginBottom: 10 }}>What can I help with?</h2>
              <p style={{ fontSize: 16, color: "var(--color-text-muted)", maxWidth: 460, textAlign: "center", lineHeight: 1.75 }}>
                Ask me to write code, analyze data, search the web, or automate tasks.
              </p>
            </div>
          ) : (
            <div style={{ maxWidth: 800, margin: "0 auto", padding: "32px 24px" }}>
              {filteredMessages.map((msg) => <MessageItem key={msg.id} msg={msg} />)}
              {isLoading && !messages.some((m) => m.id === "streaming") && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>

      {/* Agent Drawer Trigger - thin strip on right edge */}
      <div
        onMouseEnter={() => {
          if (agentsDrawerTimerRef.current) clearTimeout(agentsDrawerTimerRef.current);
          setShowAgentsDrawer(true);
        }}
        style={{ width: 12, flexShrink: 0, cursor: "pointer", background: "var(--color-bg-elevated)", borderLeft: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <Users size={10} color="var(--color-text-muted)" />
      </div>

      {/* Agent Drawer - slides out on hover */}
      {showAgentsDrawer && (
        <div
          onMouseLeave={() => {
            agentsDrawerTimerRef.current = setTimeout(() => setShowAgentsDrawer(false), 200);
          }}
          onMouseEnter={() => {
            if (agentsDrawerTimerRef.current) clearTimeout(agentsDrawerTimerRef.current);
          }}
          style={{
            position: "absolute", right: 0, top: 0, bottom: 0, width: 260,
            background: "var(--color-bg-elevated)", borderLeft: "1px solid var(--color-border-default)",
            padding: 16, overflowY: "auto", zIndex: 50,
            boxShadow: "-4px 0 24px rgba(0,0,0,0.15)",
            animation: "slideInFromRight 0.2s ease-out",
          }}
        >
          <h3 style={{ fontSize: 12, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 1.5, padding: "0 8px", marginBottom: 12 }}>Agents</h3>
          {wsAgents.length === 0
            ? <div style={{ textAlign: "center", padding: "56px 0", color: "var(--color-text-muted)", fontSize: 14 }}>No active agents</div>
            : wsAgents.map((a) => <AgentStatusCard key={a.agent_id} agent={a} />)}
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  return <ChatPageContent />;
}
