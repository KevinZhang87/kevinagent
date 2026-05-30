const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface StreamChunk {
  type: "text" | "tool_call" | "tool_result" | "status" | "error" | "done" | "agent_update";
  content: string;
  agent_id: string;
  metadata?: Record<string, unknown>;
}

export async function* streamChat(
  message: string,
  sessionId: string,
  provider: string = "openai",
  model: string = "gpt-4o",
  agentId: string = "main"
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, provider, model, agent_id: agentId }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(`HTTP error ${response.status}: ${errorText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") return;
      try {
        yield JSON.parse(data) as StreamChunk;
      } catch {
        // skip malformed chunks
      }
    }
  }
}

/** Stream chat with file attachments (uses multipart/form-data) */
export async function* streamChatWithFiles(
  message: string,
  sessionId: string,
  provider: string = "openai",
  model: string = "gpt-4o",
  files: File[] = [],
  agentId: string = "main"
): AsyncGenerator<StreamChunk> {
  const formData = new FormData();
  formData.append("message", message);
  formData.append("session_id", sessionId);
  formData.append("provider", provider);
  formData.append("model", model);
  if (agentId && agentId !== "main") {
    formData.append("agent_id", agentId);
  }
  for (const f of files) {
    formData.append("files", f);
  }

  const response = await fetch(`${API_BASE}/api/chat/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(`HTTP error ${response.status}: ${errorText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") return;
      try {
        yield JSON.parse(data) as StreamChunk;
      } catch {
        // skip malformed chunks
      }
    }
  }
}

/** Transcribe audio file to text */
export async function transcribeAudio(file: File): Promise<{ text: string; success: boolean; error?: string }> {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/chat/transcribe`, {
      method: "POST",
      body: formData,
    });
    return res.json();
  } catch (e) {
    return { text: "", success: false, error: String(e) };
  }
}

export function createWebSocket(): WebSocket {
  return new WebSocket(`${WS_BASE}/api/chat/ws`);
}

// ---- Providers ----
export async function fetchProviders() {
  const res = await fetch(`${API_BASE}/api/models/providers`);
  return res.json();
}

export async function fetchCurrentConfig() {
  const res = await fetch(`${API_BASE}/api/models/current`);
  return res.json();
}

export async function saveSettings(data: {
  api_keys: Record<string, string>;
  base_urls: Record<string, string>;
  default_provider: string;
  default_model: string;
  max_iterations: number;
  active_providers: string[];
  custom_models?: Record<string, { id: string; name: string; max_tokens: number }[]>;
}) {
  const res = await fetch(`${API_BASE}/api/models/settings/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function addCustomModel(providerId: string, modelId: string, modelName: string, maxTokens: number = 4096) {
  const res = await fetch(`${API_BASE}/api/models/providers/${providerId}/models?model_id=${encodeURIComponent(modelId)}&model_name=${encodeURIComponent(modelName)}&max_tokens=${maxTokens}`, {
    method: "POST",
  });
  return res.json();
}

export async function removeCustomModel(providerId: string, modelId: string) {
  const res = await fetch(`${API_BASE}/api/models/providers/${providerId}/models/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
  });
  return res.json();
}

// ---- Skills ----
export async function fetchSkills() {
  const res = await fetch(`${API_BASE}/api/skills`);
  return res.json();
}

export async function createSkill(data: { name: string; description: string; instruction: string }) {
  const res = await fetch(`${API_BASE}/api/skills`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateSkill(name: string, data: { description?: string; instruction?: string; is_active?: boolean }) {
  const res = await fetch(`${API_BASE}/api/skills/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteSkill(name: string) {
  const res = await fetch(`${API_BASE}/api/skills/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  return res.json();
}

export async function evolveSkills() {
  const res = await fetch(`${API_BASE}/api/skills/evolve`, {
    method: "POST",
  });
  return res.json();
}

export async function importSkills(skills: { name: string; description: string; instruction: string }[], overwrite: boolean = false) {
  const res = await fetch(`${API_BASE}/api/skills/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ skills, overwrite }),
  });
  return res.json();
}

export async function exportSkills() {
  const res = await fetch(`${API_BASE}/api/skills/export/all`);
  return res.json();
}

// ---- Agents ----
export async function fetchAgents() {
  const res = await fetch(`${API_BASE}/api/agents`);
  return res.json();
}

export async function createAgent(data: { name: string; model: string; provider: string; parent_agent_id?: string }) {
  const res = await fetch(`${API_BASE}/api/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteAgent(agentId: string) {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}`, {
    method: "DELETE",
  });
  return res.json();
}

export async function updateAgent(agentId: string, data: { model?: string; provider?: string; parent_agent_id?: string }) {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ---- Workflow ----
export async function fetchWorkflow() {
  const res = await fetch(`${API_BASE}/api/agents/workflow`);
  return res.json();
}

// ---- Chat Sessions ----
export async function createSession(data?: { title?: string; provider?: string; model?: string }) {
  const res = await fetch(`${API_BASE}/api/chat/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {}),
  });
  return res.json();
}

export async function fetchSessions() {
  const res = await fetch(`${API_BASE}/api/chat/sessions`);
  return res.json();
}

export async function fetchSessionMessages(sessionId: string, limit: number = 100) {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages?limit=${limit}`);
  return res.json();
}

export async function deleteSession(sessionId: string) {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
  return res.json();
}

// ---- Token Stats ----
export async function fetchTokenStats(days: number = 30) {
  const res = await fetch(`${API_BASE}/api/stats/tokens?days=${days}`);
  return res.json();
}

export async function fetchStatsOverview() {
  const res = await fetch(`${API_BASE}/api/stats/overview`);
  return res.json();
}

export async function fetchContextStats() {
  const res = await fetch(`${API_BASE}/api/stats/context`);
  return res.json();
}

// ---- Memories ----
export async function fetchMemories(sessionId?: string, memoryType?: string, limit: number = 200) {
  const params = new URLSearchParams();
  if (sessionId) params.set("session_id", sessionId);
  if (memoryType) params.set("memory_type", memoryType);
  params.set("limit", String(limit));
  const res = await fetch(`${API_BASE}/api/memories?${params}`);
  return res.json();
}

export async function fetchMemoryStats() {
  const res = await fetch(`${API_BASE}/api/memories/stats`);
  return res.json();
}

export async function updateMemory(memoryId: number, data: { content?: string; importance?: number; memory_type?: string }) {
  const res = await fetch(`${API_BASE}/api/memories/${memoryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteMemory(memoryId: number) {
  const res = await fetch(`${API_BASE}/api/memories/${memoryId}`, { method: "DELETE" });
  return res.json();
}

export async function cleanupMemories(maxAgeDays: number = 30, minImportance: number = 0.3, dryRun: boolean = false) {
  const res = await fetch(`${API_BASE}/api/memories/cleanup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ max_age_days: maxAgeDays, min_importance: minImportance, dry_run: dryRun }),
  });
  return res.json();
}

export async function importMarkdownSkill(content: string, overwrite: boolean = false) {
  const res = await fetch(`${API_BASE}/api/skills/import/markdown`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, overwrite }),
  });
  return res.json();
}

// ---- User Settings ----
export async function fetchUserSettings() {
  const res = await fetch(`${API_BASE}/api/user-settings`);
  return res.json();
}

export async function updateUserSettings(settings: Record<string, string>) {
  const res = await fetch(`${API_BASE}/api/user-settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings }),
  });
  return res.json();
}

// ---- Sandbox ----
export async function fetchSandboxStatus() {
  const res = await fetch(`${API_BASE}/api/sandbox/status`);
  return res.json();
}

export async function testSandbox() {
  const res = await fetch(`${API_BASE}/api/sandbox/test`, { method: "POST" });
  return res.json();
}

// ---- Scheduled Tasks ----
export async function fetchTasks() {
  const res = await fetch(`${API_BASE}/api/tasks`);
  return res.json();
}

export async function createTask(data: { name: string; message: string; interval: string; agent_id?: string }) {
  const res = await fetch(`${API_BASE}/api/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateTask(taskId: string, data: { name?: string; message?: string; interval?: string; agent_id?: string; is_active?: boolean }) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteTask(taskId: string) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
  return res.json();
}

export async function triggerTask(taskId: string) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/run`, { method: "POST" });
  return res.json();
}

export async function fetchTaskExecutions(taskId: string, limit: number = 20) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/executions?limit=${limit}`);
  return res.json();
}

export async function fetchTasksStats() {
  const res = await fetch(`${API_BASE}/api/tasks/stats`);
  return res.json();
}
