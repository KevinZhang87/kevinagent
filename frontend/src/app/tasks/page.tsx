"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchTasks, createTask, updateTask, deleteTask, triggerTask, fetchTaskExecutions, fetchAgents, fetchTasksStats } from "@/lib/api";
import { formatTime, formatDuration } from "@/lib/utils";
import {
  Clock, Plus, Play, Pause, Trash2, RefreshCw, ChevronRight, ChevronDown,
  CheckCircle2, XCircle, Loader2, Timer, Pencil, Eye,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface TaskInfo {
  task_id: string; name: string; message: string; interval: string;
  agent_id: string; is_active: boolean; is_running: boolean;
  last_run: string | null; next_run: string | null;
  run_count: number; fail_count: number; created_at: string;
}

interface ExecutionInfo {
  execution_id: string; task_id: string; status: string;
  result: string; has_more: boolean; started_at: string; finished_at: string | null; duration_ms: number;
}

const statusIcon: Record<string, React.ReactNode> = {
  success: <CheckCircle2 size={12} color="var(--color-success)" />,
  failed: <XCircle size={12} color="var(--color-error)" />,
  running: <Loader2 size={12} color="var(--color-info)" style={{ animation: "spin 1s linear infinite" }} />,
};

const inputStyle: React.CSSProperties = {
  width: "100%", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
  borderRadius: 8, padding: "10px 14px", fontSize: 14, color: "var(--color-text-primary)", outline: "none",
};

const labelStyle: React.CSSProperties = { fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 4, fontWeight: 500 };

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [stats, setStats] = useState({ total_tasks: 0, active_tasks: 0, running_tasks: 0, total_executions: 0, failed_executions: 0 });
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [agents, setAgents] = useState<{ agent_id: string; status: string }[]>([]);
  const [newTask, setNewTask] = useState({ name: "", message: "", interval: "1h", agent_id: "main" });
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [executions, setExecutions] = useState<ExecutionInfo[]>([]);
  const [execLoading, setExecLoading] = useState(false);
  const [editingTask, setEditingTask] = useState<TaskInfo | null>(null);
  const [editForm, setEditForm] = useState({ name: "", message: "", interval: "1h", agent_id: "main" });
  const [expandedExec, setExpandedExec] = useState<string | null>(null);
  const [resultViewer, setResultViewer] = useState<{ title: string; content: string; status: string } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [taskData, statsData, agentData] = await Promise.all([
        fetchTasks(), fetchTasksStats(), fetchAgents(),
      ]);
      setTasks(taskData.tasks || []);
      setStats(statsData);
      setAgents(agentData.agents || []);
    } catch (e) { console.error("Failed to load tasks:", e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCreate = async () => {
    if (!newTask.name.trim() || !newTask.message.trim()) return;
    try {
      await createTask(newTask);
      setShowCreate(false);
      setNewTask({ name: "", message: "", interval: "1h", agent_id: "main" });
      await loadData();
    } catch (e) { console.error("Failed to create task:", e); }
  };

  const handleToggle = async (task: TaskInfo) => {
    try {
      await updateTask(task.task_id, { is_active: !task.is_active });
      await loadData();
    } catch (e) { console.error("Failed to toggle task:", e); }
  };

  const handleDelete = async (taskId: string) => {
    if (!confirm("Delete this task and its execution history?")) return;
    try {
      await deleteTask(taskId);
      if (expandedTask === taskId) setExpandedTask(null);
      await loadData();
    } catch (e) { console.error("Failed to delete task:", e); }
  };

  const handleRunNow = async (taskId: string) => {
    try {
      await triggerTask(taskId);
      await loadData();
      if (expandedTask === taskId) await loadExecutions(taskId);
    } catch (e) { console.error("Failed to trigger task:", e); }
  };

  const loadExecutions = async (taskId: string) => {
    setExecLoading(true);
    try {
      const data = await fetchTaskExecutions(taskId);
      setExecutions(data.executions || []);
    } catch (e) { console.error("Failed to load executions:", e); }
    finally { setExecLoading(false); }
  };

  const toggleExpand = (taskId: string) => {
    if (expandedTask === taskId) {
      setExpandedTask(null);
    } else {
      setExpandedTask(taskId);
      loadExecutions(taskId);
    }
  };

  const openEdit = (task: TaskInfo) => {
    setEditingTask(task);
    setEditForm({ name: task.name, message: task.message, interval: task.interval, agent_id: task.agent_id });
  };

  const handleEdit = async () => {
    if (!editingTask || !editForm.name.trim() || !editForm.message.trim()) return;
    try {
      await updateTask(editingTask.task_id, editForm);
      setEditingTask(null);
      await loadData();
    } catch (e) { console.error("Failed to update task:", e); }
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <header style={{ height: 56, borderBottom: "1px solid var(--color-border-default)", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, background: "var(--color-bg-elevated)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Clock size={14} color="var(--color-text-muted)" />
          <span style={{ fontSize: 14, fontWeight: 600 }}>Scheduled Tasks</span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => setShowCreate(true)} style={{ display: "flex", alignItems: "center", gap: 5, height: 30, padding: "0 12px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
            <Plus size={12} /> New Task
          </button>
          <button onClick={loadData} disabled={loading} style={{ display: "flex", alignItems: "center", gap: 5, height: 30, padding: "0 12px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>
            <RefreshCw size={12} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
          </button>
        </div>
      </header>

      {/* Stats cards */}
      <div style={{ display: "flex", gap: 8, padding: "12px 16px", borderBottom: "1px solid var(--color-border-default)", background: "var(--color-bg-secondary)" }}>
        {[
          { label: "Total", value: stats.total_tasks, color: "var(--color-text-primary)" },
          { label: "Active", value: stats.active_tasks, color: "var(--color-success)" },
          { label: "Running", value: stats.running_tasks, color: "var(--color-info)" },
          { label: "Executions", value: stats.total_executions, color: "var(--color-text-primary)" },
          { label: "Failed", value: stats.failed_executions, color: "var(--color-error)" },
        ].map((s) => (
          <div key={s.label} style={{ flex: 1, background: "var(--color-bg-card)", borderRadius: 8, padding: "8px 12px", border: "1px solid var(--color-border-default)" }}>
            <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginBottom: 2 }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Task list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px" }}>
        {tasks.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 0", color: "var(--color-text-muted)" }}>
            <Clock size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
            <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>No scheduled tasks</div>
            <div style={{ fontSize: 12 }}>Create a task to run agent actions on schedule</div>
          </div>
        ) : tasks.map((task) => (
          <div key={task.task_id} style={{ background: "var(--color-bg-card)", borderRadius: 8, border: "1px solid var(--color-border-default)", marginBottom: 8, overflow: "hidden" }}>
            {/* Task header */}
            <div style={{ display: "flex", alignItems: "center", padding: "10px 14px", gap: 10 }}>
              <button onClick={() => toggleExpand(task.task_id)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 0, display: "flex" }}>
                {expandedTask === task.task_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>

              <div style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: task.is_active ? (task.is_running ? "var(--color-info)" : "var(--color-success)") : "var(--color-text-muted)", boxShadow: task.is_running ? "0 0 6px rgba(59,130,246,0.4)" : "none" }} />

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)" }}>{task.name}</span>
                  <span style={{ fontSize: 10, color: "var(--color-text-muted)", background: "var(--color-bg-secondary)", padding: "1px 6px", borderRadius: 4 }}>{task.interval}</span>
                  {task.agent_id !== "main" && (
                    <span style={{ fontSize: 10, color: "var(--color-info)", background: "rgba(59,130,246,0.1)", padding: "1px 6px", borderRadius: 4 }}>{task.agent_id}</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {task.message}
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: "var(--color-text-muted)" }}>
                <span>{task.run_count} runs</span>
                {task.fail_count > 0 && <span style={{ color: "var(--color-error)" }}>{task.fail_count} fail</span>}
              </div>

              <div style={{ display: "flex", gap: 4 }}>
                <button onClick={() => handleRunNow(task.task_id)} title="Run now" style={{ background: "none", border: "1px solid var(--color-border-default)", borderRadius: 5, padding: "3px 6px", cursor: "pointer", color: "var(--color-info)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                  <Play size={10} /> Run
                </button>
                <button onClick={() => openEdit(task)} title="Edit" style={{ background: "none", border: "1px solid var(--color-border-default)", borderRadius: 5, padding: "3px 6px", cursor: "pointer", color: "var(--color-text-secondary)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                  <Pencil size={10} /> Edit
                </button>
                <button onClick={() => handleToggle(task)} title={task.is_active ? "Pause" : "Resume"} style={{ background: "none", border: "1px solid var(--color-border-default)", borderRadius: 5, padding: "3px 6px", cursor: "pointer", color: task.is_active ? "var(--color-warning)" : "var(--color-success)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                  {task.is_active ? <><Pause size={10} /> Pause</> : <><Play size={10} /> Resume</>}
                </button>
                <button onClick={() => handleDelete(task.task_id)} title="Delete" style={{ background: "none", border: "1px solid var(--color-border-default)", borderRadius: 5, padding: "3px 6px", cursor: "pointer", color: "var(--color-error)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                  <Trash2 size={10} />
                </button>
              </div>
            </div>

            {/* Metadata row */}
            <div style={{ display: "flex", gap: 16, padding: "0 14px 8px 42", fontSize: 10, color: "var(--color-text-muted)" }}>
              <span>Last: {formatTime(task.last_run)}</span>
              <span>Next: {task.is_active ? formatTime(task.next_run) : "Paused"}</span>
            </div>

            {/* Execution history */}
            {expandedTask === task.task_id && (
              <div style={{ borderTop: "1px solid var(--color-border-default)", background: "var(--color-bg-secondary)" }}>
                <div style={{ padding: "8px 14px", fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)" }}>
                  Execution History
                </div>
                {execLoading ? (
                  <div style={{ padding: 12, textAlign: "center", fontSize: 11, color: "var(--color-text-muted)" }}>
                    <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Loading...
                  </div>
                ) : executions.length === 0 ? (
                  <div style={{ padding: 12, textAlign: "center", fontSize: 11, color: "var(--color-text-muted)" }}>No executions yet</div>
                ) : executions.map((exec) => (
                  <div key={exec.execution_id} style={{ borderTop: "1px solid var(--color-border-default)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 14px" }}>
                      <div style={{ flexShrink: 0 }}>{statusIcon[exec.status] || <Timer size={12} color="var(--color-text-muted)" />}</div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, flex: 1 }}>
                        <span style={{ color: "var(--color-text-secondary)" }}>{formatTime(exec.started_at)}</span>
                        <span style={{ color: "var(--color-text-muted)" }}>{formatDuration(exec.duration_ms)}</span>
                      </div>
                      {exec.result && (
                        <div style={{ display: "flex", gap: 4 }}>
                          <button onClick={() => setExpandedExec(expandedExec === exec.execution_id ? null : exec.execution_id)} title="Toggle preview" style={{ background: "none", border: "1px solid var(--color-border-default)", borderRadius: 4, padding: "2px 6px", cursor: "pointer", color: "var(--color-text-muted)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                            {expandedExec === exec.execution_id ? <ChevronDown size={10} /> : <ChevronRight size={10} />} Preview
                          </button>
                          <button onClick={() => setResultViewer({ title: `${task.name} — ${formatTime(exec.started_at)}`, content: exec.result, status: exec.status })} title="View full result" style={{ background: "none", border: "1px solid var(--color-border-default)", borderRadius: 4, padding: "2px 6px", cursor: "pointer", color: "var(--color-info)", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                            <Eye size={10} /> View
                          </button>
                        </div>
                      )}
                    </div>
                    {/* Inline markdown preview */}
                    {expandedExec === exec.execution_id && exec.result && (
                      <div style={{ padding: "0 14px 10px 36", maxHeight: 200, overflowY: "auto", borderTop: "1px dashed var(--color-border-default)" }}>
                        <div style={{ background: "var(--color-bg-card)", borderRadius: 6, padding: "8px 12px", fontSize: 12, lineHeight: 1.6, color: "var(--color-text-secondary)" }}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{exec.result.slice(0, 1500)}</ReactMarkdown>
                          {(exec.has_more || exec.result.length > 1500) && (
                            <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 4, fontStyle: "italic" }}>
                              Content truncated — click "View" to see full result
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Create Task Dialog */}
      {showCreate && (
        <>
          <div onClick={() => setShowCreate(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 99, backdropFilter: "blur(2px)" }} />
          <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 12, padding: "18px 20px", width: 380, boxShadow: "0 12px 40px rgba(0,0,0,0.5)", zIndex: 100 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 16px" }}>New Scheduled Task</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={labelStyle}>Name</label>
                <input type="text" value={newTask.name} onChange={(e) => setNewTask((p) => ({ ...p, name: e.target.value }))} placeholder="e.g. Daily Summary" style={inputStyle} autoFocus />
              </div>
              <div>
                <label style={labelStyle}>Prompt Message</label>
                <textarea value={newTask.message} onChange={(e) => setNewTask((p) => ({ ...p, message: e.target.value }))} placeholder="e.g. Summarize the latest news about AI" rows={3} style={{ ...inputStyle, resize: "vertical", minHeight: 60 }} />
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Interval</label>
                  <select value={newTask.interval} onChange={(e) => setNewTask((p) => ({ ...p, interval: e.target.value }))} style={inputStyle}>
                    <option value="30s">30 seconds</option>
                    <option value="1m">1 minute</option>
                    <option value="5m">5 minutes</option>
                    <option value="10m">10 minutes</option>
                    <option value="30m">30 minutes</option>
                    <option value="1h">1 hour</option>
                    <option value="6h">6 hours</option>
                    <option value="12h">12 hours</option>
                    <option value="1d">1 day</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Agent</label>
                  <select value={newTask.agent_id} onChange={(e) => setNewTask((p) => ({ ...p, agent_id: e.target.value }))} style={inputStyle}>
                    <option value="main">Main Agent</option>
                    {agents.filter((a) => a.agent_id !== "main").map((a) => (
                      <option key={a.agent_id} value={a.agent_id}>{a.agent_id}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, marginTop: 4 }}>
                <button onClick={() => setShowCreate(false)} style={{ padding: "6px 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>Cancel</button>
                <button onClick={handleCreate} disabled={!newTask.name.trim() || !newTask.message.trim()} style={{ padding: "6px 14px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer", opacity: (!newTask.name.trim() || !newTask.message.trim()) ? 0.4 : 1 }}>Create</button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Edit Task Dialog */}
      {editingTask && (
        <>
          <div onClick={() => setEditingTask(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 99, backdropFilter: "blur(2px)" }} />
          <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 12, padding: "18px 20px", width: 380, boxShadow: "0 12px 40px rgba(0,0,0,0.5)", zIndex: 100 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 16px" }}>Edit Task</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={labelStyle}>Name</label>
                <input type="text" value={editForm.name} onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))} style={inputStyle} autoFocus />
              </div>
              <div>
                <label style={labelStyle}>Prompt Message</label>
                <textarea value={editForm.message} onChange={(e) => setEditForm((p) => ({ ...p, message: e.target.value }))} rows={3} style={{ ...inputStyle, resize: "vertical", minHeight: 60 }} />
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Interval</label>
                  <select value={editForm.interval} onChange={(e) => setEditForm((p) => ({ ...p, interval: e.target.value }))} style={inputStyle}>
                    <option value="30s">30 seconds</option>
                    <option value="1m">1 minute</option>
                    <option value="5m">5 minutes</option>
                    <option value="10m">10 minutes</option>
                    <option value="30m">30 minutes</option>
                    <option value="1h">1 hour</option>
                    <option value="6h">6 hours</option>
                    <option value="12h">12 hours</option>
                    <option value="1d">1 day</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Agent</label>
                  <select value={editForm.agent_id} onChange={(e) => setEditForm((p) => ({ ...p, agent_id: e.target.value }))} style={inputStyle}>
                    <option value="main">Main Agent</option>
                    {agents.filter((a) => a.agent_id !== "main").map((a) => (
                      <option key={a.agent_id} value={a.agent_id}>{a.agent_id}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, marginTop: 4 }}>
                <button onClick={() => setEditingTask(null)} style={{ padding: "6px 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>Cancel</button>
                <button onClick={handleEdit} disabled={!editForm.name.trim() || !editForm.message.trim()} style={{ padding: "6px 14px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer", opacity: (!editForm.name.trim() || !editForm.message.trim()) ? 0.4 : 1 }}>Save</button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Result Viewer Dialog */}
      {resultViewer && (
        <>
          <div onClick={() => setResultViewer(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 99, backdropFilter: "blur(2px)" }} />
          <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 12, width: "min(720px, 90vw)", maxHeight: "80vh", display: "flex", flexDirection: "column", boxShadow: "0 12px 40px rgba(0,0,0,0.5)", zIndex: 100 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid var(--color-border-default)", flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {statusIcon[resultViewer.status] || <Timer size={14} color="var(--color-text-muted)" />}
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)" }}>{resultViewer.title}</span>
              </div>
              <button onClick={() => setResultViewer(null)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}>&times;</button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "16px 18px" }}>
              <div className="markdown-body" style={{ fontSize: 13, lineHeight: 1.7, color: "var(--color-text-secondary)" }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{resultViewer.content}</ReactMarkdown>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
