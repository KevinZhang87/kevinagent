"use client";

import { memo, useMemo, useState } from "react";
import { User, Bot, Wrench, AlertCircle, ChevronRight, ChevronDown, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

interface ToolCallInfo {
  name: string;
  args: Record<string, unknown>;
  output?: string;
  success?: boolean;
  error?: string;
  status: "calling" | "done" | "error";
}

interface TaskPlanItem {
  id: number;
  description: string;
  status: "pending" | "in_progress" | "completed" | "failed";
}

interface Message {
  id: string;
  role: "user" | "assistant" | "tool" | "system" | "error" | "tool_group" | "task_plan";
  content: string;
  toolCalls?: ToolCallInfo[];
  toolResult?: { name: string; success: boolean; output: string };
  agentId?: string;
  timestamp: Date;
  taskPlan?: TaskPlanItem[];
}

function ToolItem({ tc, isLast }: { tc: ToolCallInfo; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = tc.status !== "calling" && (tc.output || tc.error);
  const hasSubActivity = tc.name === "call_agent" && tc.subActivity && tc.subActivity.length > 0;
  const isClickable = hasDetail || hasSubActivity;

  // Auto-expand when sub-agent activity is streaming
  const showSubActivity = hasSubActivity && (tc.status === "calling" || expanded);

  return (
    <div style={{ borderBottom: isLast ? "none" : "1px solid var(--color-border-default)" }}>
      {/* Tool header - clickable to expand/collapse */}
      <div
        style={{ padding: "8px 14px", display: "flex", alignItems: "center", gap: 8, cursor: isClickable ? "pointer" : "default" }}
        onClick={() => isClickable && setExpanded(!expanded)}
      >
        {isClickable ? (
          expanded ? <ChevronDown size={12} color="var(--color-text-muted)" style={{ flexShrink: 0 }} /> : <ChevronRight size={12} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
        ) : (
          <ChevronRight size={12} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
        )}
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-secondary)" }}>{tc.name}</span>
        {tc.name === "call_agent" && tc.args?.agent_id && (
          <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 4, background: "rgba(139,92,246,0.1)", color: "#a78bfa" }}>
            {String(tc.args.agent_id)}
          </span>
        )}
        {tc.status === "calling" ? (
          <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 4, background: "rgba(59,130,246,0.1)", color: "#60a5fa", display: "flex", alignItems: "center", gap: 4 }}>
            <Loader2 size={10} style={{ animation: "spin 1s linear infinite" }} />
            {hasSubActivity ? `running (${tc.subActivity.length} events)` : "calling"}
          </span>
        ) : tc.status === "done" ? (
          <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 4, background: "rgba(34,197,94,0.1)", color: "var(--color-success)" }}>ok</span>
        ) : (
          <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 4, background: "rgba(239,68,68,0.1)", color: "var(--color-error)" }}>err</span>
        )}
      </div>
      {/* Sub-agent activity: show during execution */}
      {showSubActivity && tc.subActivity && (
        <div style={{ padding: "4px 14px 8px 36px" }}>
          <div style={{ border: "1px solid var(--color-border-default)", borderRadius: 8, overflow: "hidden" }}>
            {tc.subActivity.map((act, j) => (
              <div key={j} style={{ padding: "6px 10px", borderBottom: j < tc.subActivity!.length - 1 ? "1px solid var(--color-border-default)" : "none", fontSize: 11 }}>
                {act.type === "text" ? (
                  <div style={{ color: "var(--color-text-secondary)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                    {act.content.slice(0, 300)}{act.content.length > 300 ? "..." : ""}
                  </div>
                ) : act.type === "tool_call" ? (
                  <div style={{ color: "#60a5fa", display: "flex", alignItems: "center", gap: 4 }}>
                    <Wrench size={10} />
                    <span>calling: {(() => { try { return JSON.parse(act.content).name; } catch { return act.content.slice(0, 50); } })()}</span>
                  </div>
                ) : act.type === "tool_result" ? (
                  <div style={{ color: "var(--color-success)", display: "flex", alignItems: "center", gap: 4 }}>
                    <span>✓</span>
                    <span>{(() => { try { const r = JSON.parse(act.content); return `${r.name} ${r.success ? "ok" : "err"}`; } catch { return "result"; } })()}</span>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}
      {/* Args + Result: collapsed by default */}
      {expanded && !hasSubActivity && (
        <>
          <div style={{ padding: "0 14px 6px 36px" }}>
            <pre style={{ fontSize: 11, color: "var(--color-text-muted)", background: "var(--color-bg-elevated)", borderRadius: 6, padding: "6px 10px", margin: 0, fontFamily: "'SF Mono','Cascadia Code','Consolas',monospace", lineHeight: 1.5, overflow: "auto" }}>
              {JSON.stringify(tc.args, null, 2)}
            </pre>
          </div>
          {hasDetail && (
            <div style={{ padding: "0 14px 10px 36px" }}>
              <pre style={{ fontSize: 12, color: "var(--color-text-muted)", background: "var(--color-bg-elevated)", borderRadius: 6, padding: "8px 12px", margin: 0, fontFamily: "'SF Mono','Cascadia Code','Consolas',monospace", lineHeight: 1.6, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {tc.error ? tc.error : tc.output?.slice(0, 800)}
              </pre>
            </div>
          )}
        </>
      )}
      {/* Show final output after completion when expanded */}
      {expanded && hasSubActivity && hasDetail && (
        <div style={{ padding: "0 14px 10px 36px" }}>
          <pre style={{ fontSize: 12, color: "var(--color-text-muted)", background: "var(--color-bg-elevated)", borderRadius: 6, padding: "8px 12px", margin: 0, fontFamily: "'SF Mono','Cascadia Code','Consolas',monospace", lineHeight: 1.6, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {tc.error ? tc.error : tc.output?.slice(0, 800)}
          </pre>
        </div>
      )}
    </div>
  );
}

export const ChatMessage = memo(function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isTool = message.role === "tool";
  const isError = message.role === "error";
  const isToolGroup = message.role === "tool_group";
  const showAgentBadge = !isUser && !isError && message.agentId && message.agentId !== "main";

  if (isToolGroup) {
    const tools = message.toolCalls || [];
    if (tools.length === 0) return null;
    return (
      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 4 }}>
          <Wrench size={15} color="var(--color-text-muted)" />
        </div>
        <div style={{ flex: 1, minWidth: 0, border: "1px solid var(--color-border-default)", borderRadius: 12, background: "var(--color-bg-secondary)", overflow: "hidden" }}>
          {/* Header */}
          <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--color-text-muted)", fontWeight: 600 }}>
            <span>Tool Calls</span>
            {showAgentBadge && (
              <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 4, background: "rgba(139,92,246,0.1)", color: "#a78bfa", fontWeight: 500 }}>{message.agentId}</span>
            )}
            <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 400, opacity: 0.7 }}>{tools.length} tool{tools.length > 1 ? "s" : ""}</span>
          </div>
          {/* Tool items */}
          <div>
            {tools.map((tc, i) => (
              <ToolItem key={i} tc={tc} isLast={i < tools.length - 1} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isTool) {
    return (
      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 4 }}>
          <Wrench size={15} color="var(--color-text-muted)" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-muted)" }}>{message.toolResult?.name || "tool"}</span>
            {message.toolResult && (
              <span style={{ fontSize: 12, padding: "2px 10px", borderRadius: 6, background: message.toolResult.success ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)", color: message.toolResult.success ? "var(--color-success)" : "var(--color-error)" }}>
                {message.toolResult.success ? "ok" : "err"}
              </span>
            )}
          </div>
          <pre style={{ fontSize: 13, color: "var(--color-text-muted)", background: "var(--color-bg-secondary)", borderRadius: 10, padding: 16, overflow: "auto", fontFamily: "'SF Mono','Cascadia Code','Consolas',monospace", lineHeight: 1.7, margin: 0, border: "1px solid var(--color-border-default)" }}>
            {message.toolResult ? message.toolResult.output.slice(0, 500) : message.content}
          </pre>
        </div>
      </div>
    );
  }

  if (message.role === "task_plan" && message.taskPlan) {
    const statusIcons: Record<string, string> = {
      pending: "⏳",
      in_progress: "🔄",
      completed: "✅",
      failed: "❌",
    };
    const statusColors: Record<string, string> = {
      pending: "var(--color-text-muted)",
      in_progress: "#60a5fa",
      completed: "var(--color-success)",
      failed: "var(--color-error)",
    };
    const completedCount = message.taskPlan.filter(t => t.status === "completed").length;
    const totalCount = message.taskPlan.length;

    return (
      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 4 }}>
          <span style={{ fontSize: 14 }}>📋</span>
        </div>
        <div style={{ flex: 1, minWidth: 0, border: "1px solid var(--color-border-default)", borderRadius: 12, background: "var(--color-bg-secondary)", overflow: "hidden" }}>
          {/* Header */}
          <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text-secondary)" }}>任务规划</span>
            <span style={{ fontSize: 11, padding: "1px 8px", borderRadius: 4, background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>
              {completedCount}/{totalCount} 完成
            </span>
            {/* Progress bar */}
            <div style={{ flex: 1, height: 4, background: "var(--color-bg-elevated)", borderRadius: 999, overflow: "hidden" }}>
              <div style={{ width: `${(completedCount / totalCount) * 100}%`, height: "100%", background: completedCount === totalCount ? "var(--color-success)" : "#60a5fa", transition: "width 0.3s ease" }} />
            </div>
          </div>
          {/* Task list */}
          <div style={{ padding: "8px 0" }}>
            {message.taskPlan.map((task, i) => (
              <div key={task.id} style={{ padding: "6px 14px", display: "flex", alignItems: "flex-start", gap: 8, opacity: task.status === "pending" ? 0.6 : 1 }}>
                <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1 }}>{statusIcons[task.status]}</span>
                <span style={{ fontSize: 13, color: statusColors[task.status], lineHeight: 1.5, textDecoration: task.status === "completed" ? "line-through" : "none" }}>
                  {task.description}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.15)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 4 }}>
          <AlertCircle size={15} color="var(--color-error)" />
        </div>
        <div style={{ fontSize: 15, color: "var(--color-error)", background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.12)", borderRadius: 14, padding: "14px 20px" }}>
          {message.content}
        </div>
      </div>
    );
  }

  // Markdown components for assistant messages
  const markdownComponents = useMemo(() => ({
    p: ({ children }: { children?: React.ReactNode }) => (
      <p style={{ margin: "0 0 12px 0", lineHeight: 1.75 }}>{children}</p>
    ),
    h1: ({ children }: { children?: React.ReactNode }) => (
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: "20px 0 12px 0", lineHeight: 1.4 }}>{children}</h1>
    ),
    h2: ({ children }: { children?: React.ReactNode }) => (
      <h2 style={{ fontSize: 20, fontWeight: 700, margin: "18px 0 10px 0", lineHeight: 1.4 }}>{children}</h2>
    ),
    h3: ({ children }: { children?: React.ReactNode }) => (
      <h3 style={{ fontSize: 17, fontWeight: 600, margin: "16px 0 8px 0", lineHeight: 1.4 }}>{children}</h3>
    ),
    ul: ({ children }: { children?: React.ReactNode }) => (
      <ul style={{ margin: "0 0 12px 0", paddingLeft: 24, lineHeight: 1.75 }}>{children}</ul>
    ),
    ol: ({ children }: { children?: React.ReactNode }) => (
      <ol style={{ margin: "0 0 12px 0", paddingLeft: 24, lineHeight: 1.75 }}>{children}</ol>
    ),
    li: ({ children }: { children?: React.ReactNode }) => (
      <li style={{ marginBottom: 4 }}>{children}</li>
    ),
    blockquote: ({ children }: { children?: React.ReactNode }) => (
      <blockquote style={{ borderLeft: "3px solid var(--color-border-hover)", margin: "0 0 12px 0", padding: "4px 16px", color: "var(--color-text-secondary)", background: "var(--color-bg-secondary)", borderRadius: "0 8px 8px 0" }}>{children}</blockquote>
    ),
    code: ({ className, children }: { className?: string; children?: React.ReactNode }) => {
      const isInline = !className;
      return isInline ? (
        <code style={{ background: "var(--color-bg-elevated)", padding: "2px 6px", borderRadius: 4, fontSize: 14, fontFamily: "'SF Mono','Cascadia Code','Consolas',monospace" }}>{children}</code>
      ) : (
        <code className={className}>{children}</code>
      );
    },
    pre: ({ children }: { children?: React.ReactNode }) => (
      <pre style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 10, padding: 16, margin: "0 0 12px 0", overflow: "auto", fontFamily: "'SF Mono','Cascadia Code','Consolas',monospace", fontSize: 13, lineHeight: 1.6 }}>{children}</pre>
    ),
    table: ({ children }: { children?: React.ReactNode }) => (
      <div style={{ overflowX: "auto", margin: "0 0 12px 0" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>{children}</table>
      </div>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
      <th style={{ border: "1px solid var(--color-border-default)", padding: "8px 12px", background: "var(--color-bg-elevated)", fontWeight: 600, textAlign: "left" }}>{children}</th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
      <td style={{ border: "1px solid var(--color-border-default)", padding: "8px 12px" }}>{children}</td>
    ),
    a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
      <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-info)", textDecoration: "underline" }}>{children}</a>
    ),
    hr: () => (
      <hr style={{ border: "none", borderTop: "1px solid var(--color-border-default)", margin: "16px 0" }} />
    ),
    strong: ({ children }: { children?: React.ReactNode }) => (
      <strong style={{ fontWeight: 600 }}>{children}</strong>
    ),
  }), []);

  return (
    <div style={{ display: "flex", gap: 16, flexDirection: isUser ? "row-reverse" : "row" }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 4,
        background: isUser ? "var(--color-bg-elevated)" : showAgentBadge ? "rgba(139,92,246,0.1)" : "var(--color-bg-card)",
        border: `1px solid ${showAgentBadge ? "rgba(139,92,246,0.3)" : "var(--color-border-default)"}`,
      }}>
        {isUser ? <User size={15} color="var(--color-text-secondary)" /> : <Bot size={15} color={showAgentBadge ? "#a78bfa" : "var(--color-text-muted)"} />}
      </div>
      <div style={{
        maxWidth: "80%", fontSize: 16, lineHeight: 1.75, wordBreak: "break-word",
        ...(isUser
          ? { background: "var(--color-bg-elevated)", color: "var(--color-text-primary)", borderRadius: "18px 18px 4px 18px", padding: "14px 20px", border: "1px solid var(--color-border-default)", whiteSpace: "pre-wrap" }
          : {}),
        ...(showAgentBadge && !isUser
          ? { borderLeft: "3px solid rgba(139,92,246,0.4)", paddingLeft: 16 }
          : {}),
      }}>
        {showAgentBadge && !isUser && (
          <div style={{
            fontSize: 11, padding: "2px 10px", borderRadius: 4,
            background: "rgba(139,92,246,0.1)", color: "#a78bfa",
            fontWeight: 600, display: "inline-block", marginBottom: 8,
            letterSpacing: "0.5px",
          }}>
            🤖 {message.agentId}
          </div>
        )}
        {isUser ? (
          message.content
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]} components={markdownComponents}>
            {message.content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
});

export function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Bot size={15} color="var(--color-text-muted)" />
      </div>
      <div style={{ display: "flex", gap: 7, padding: "14px 0" }}>
        <span className="typing-dot" style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-text-muted)" }} />
        <span className="typing-dot" style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-text-muted)" }} />
        <span className="typing-dot" style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-text-muted)" }} />
      </div>
    </div>
  );
}
