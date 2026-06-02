const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

// ---- Auth helpers ----
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

export function setAuthToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("auth_token", token);
  }
}

export function clearAuthToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("auth_token");
  }
}

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

function handleAuthError(res: Response) {
  if (res.status === 401) {
    clearAuthToken();
    localStorage.removeItem("user_info");
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
}

export interface StreamChunk {
  type: "text" | "tool_call" | "tool_result" | "status" | "error" | "done" | "agent_update";
  content: string;
  agent_id: string;
  metadata?: Record<string, unknown>;
}

// ---- Auth API ----
export async function register(email: string, password: string, name?: string) {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMe() {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    if (res.status === 401) return null;
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}

export async function* streamChat(
  message: string,
  sessionId: string,
  provider: string = "",
  model: string = "",
  agentId: string = "main"
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ message, session_id: sessionId, provider, model, agent_id: agentId }),
  });

  if (!response.ok) {
    handleAuthError(response);
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
  provider: string = "",
  model: string = "",
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
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    handleAuthError(response);
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
  const token = getAuthToken();
  const url = token ? `${WS_BASE}/api/chat/ws?token=${token}` : `${WS_BASE}/api/chat/ws`;
  return new WebSocket(url);
}

// ---- Providers ----
export async function fetchProviders() {
  const res = await fetch(`${API_BASE}/api/models/providers`, { headers: authHeaders() });
  return res.json();
}

export async function fetchCurrentConfig() {
  const res = await fetch(`${API_BASE}/api/models/current`, { headers: authHeaders() });
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
  memory_backend?: string;
  memory_config?: Record<string, unknown>;
}) {
  const res = await fetch(`${API_BASE}/api/models/settings/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function addCustomModel(providerId: string, modelId: string, modelName: string, maxTokens: number = 4096) {
  const res = await fetch(`${API_BASE}/api/models/providers/${providerId}/models?model_id=${encodeURIComponent(modelId)}&model_name=${encodeURIComponent(modelName)}&max_tokens=${maxTokens}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function removeCustomModel(providerId: string, modelId: string) {
  const res = await fetch(`${API_BASE}/api/models/providers/${providerId}/models/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ---- Skills ----
export async function fetchSkills() {
  const res = await fetch(`${API_BASE}/api/skills`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

export async function createSkill(data: { name: string; description: string; instruction: string }) {
  const res = await fetch(`${API_BASE}/api/skills`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateSkill(name: string, data: { description?: string; instruction?: string; is_active?: boolean }) {
  const res = await fetch(`${API_BASE}/api/skills/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteSkill(name: string) {
  const res = await fetch(`${API_BASE}/api/skills/${encodeURIComponent(name)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return res.json();
}

export async function evolveSkills() {
  const res = await fetch(`${API_BASE}/api/skills/evolve`, {
    method: "POST",
    headers: authHeaders(),
  });
  return res.json();
}

export async function importSkills(skills: { name: string; description: string; instruction: string }[], overwrite: boolean = false) {
  const res = await fetch(`${API_BASE}/api/skills/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ skills, overwrite }),
  });
  return res.json();
}

export async function exportSkills() {
  const res = await fetch(`${API_BASE}/api/skills/export/all`, { headers: authHeaders() });
  return res.json();
}

// ---- Agents ----
export async function fetchAgents() {
  const res = await fetch(`${API_BASE}/api/agents`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

export async function createAgent(data: {
  name: string; model: string; provider: string; parent_agent_id?: string;
  system_prompt?: string; description?: string; capabilities?: string[]; tools?: string[];
}) {
  const res = await fetch(`${API_BASE}/api/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fetchAgentDetail(agentId: string) {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

export async function cancelAgent(agentId: string) {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}/cancel`, {
    method: "POST",
    headers: authHeaders(),
  });
  return res.json();
}

export async function deleteAgent(agentId: string) {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `Delete failed: ${res.status}`);
  }
  return res.json();
}

export async function updateAgent(agentId: string, data: {
  model?: string; provider?: string; parent_agent_id?: string;
  system_prompt?: string; description?: string; capabilities?: string[]; tools?: string[];
}) {
  const res = await fetch(`${API_BASE}/api/agents/${encodeURIComponent(agentId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ---- Workflow ----
export async function fetchWorkflow() {
  const res = await fetch(`${API_BASE}/api/agents/workflow`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

// ---- Chat Sessions ----
export async function createSession(data?: { title?: string; provider?: string; model?: string }) {
  const res = await fetch(`${API_BASE}/api/chat/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data || {}),
  });
  return res.json();
}

export async function fetchSessions() {
  const res = await fetch(`${API_BASE}/api/chat/sessions`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

export async function fetchSessionMessages(sessionId: string, limit: number = 100) {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages?limit=${limit}`, { headers: authHeaders() });
  return res.json();
}

export async function deleteSession(sessionId: string) {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return res.json();
}

// ---- Token Stats ----
export async function fetchTokenStats(days: number = 30) {
  const res = await fetch(`${API_BASE}/api/stats/tokens?days=${days}`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

export async function fetchStatsOverview() {
  const res = await fetch(`${API_BASE}/api/stats/overview`, { headers: authHeaders() });
  return res.json();
}

export async function fetchContextStats() {
  const res = await fetch(`${API_BASE}/api/stats/context`, { headers: authHeaders() });
  return res.json();
}

// ---- Memories ----
export async function fetchMemories(sessionId?: string, memoryType?: string, limit: number = 200) {
  const params = new URLSearchParams();
  if (sessionId) params.set("session_id", sessionId);
  if (memoryType) params.set("memory_type", memoryType);
  params.set("limit", String(limit));
  const res = await fetch(`${API_BASE}/api/memories?${params}`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

export async function fetchMemoryStats() {
  const res = await fetch(`${API_BASE}/api/memories/stats`, { headers: authHeaders() });
  return res.json();
}

export async function updateMemory(memoryId: number, data: { content?: string; importance?: number; memory_type?: string }) {
  const res = await fetch(`${API_BASE}/api/memories/${memoryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteMemory(memoryId: number) {
  const res = await fetch(`${API_BASE}/api/memories/${memoryId}`, { method: "DELETE", headers: authHeaders() });
  return res.json();
}

export async function cleanupMemories(maxAgeDays: number = 30, minImportance: number = 0.3, dryRun: boolean = false) {
  const res = await fetch(`${API_BASE}/api/memories/cleanup`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ max_age_days: maxAgeDays, min_importance: minImportance, dry_run: dryRun }),
  });
  return res.json();
}

export async function importMarkdownSkill(content: string, overwrite: boolean = false) {
  const res = await fetch(`${API_BASE}/api/skills/import/markdown`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ content, overwrite }),
  });
  return res.json();
}

// ---- User Settings ----
export async function fetchUserSettings() {
  const res = await fetch(`${API_BASE}/api/user-settings`, { headers: authHeaders() });
  return res.json();
}

export async function updateUserSettings(settings: Record<string, string>) {
  const res = await fetch(`${API_BASE}/api/user-settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ settings }),
  });
  return res.json();
}

// ---- Sandbox ----
export async function fetchSandboxStatus() {
  const res = await fetch(`${API_BASE}/api/sandbox/status`, { headers: authHeaders() });
  return res.json();
}

export async function testSandbox() {
  const res = await fetch(`${API_BASE}/api/sandbox/test`, { method: "POST", headers: authHeaders() });
  return res.json();
}

// ---- Scheduled Tasks ----
export async function fetchTasks() {
  const res = await fetch(`${API_BASE}/api/tasks`, { headers: authHeaders() });
  handleAuthError(res);
  return res.json();
}

export async function createTask(data: { name: string; message: string; interval: string; agent_id?: string }) {
  const res = await fetch(`${API_BASE}/api/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateTask(taskId: string, data: { name?: string; message?: string; interval?: string; agent_id?: string; is_active?: boolean }) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteTask(taskId: string) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE", headers: authHeaders() });
  return res.json();
}

export async function triggerTask(taskId: string) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/run`, { method: "POST", headers: authHeaders() });
  return res.json();
}

export async function fetchTaskExecutions(taskId: string, limit: number = 20) {
  const res = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/executions?limit=${limit}`, { headers: authHeaders() });
  return res.json();
}

export async function fetchTasksStats() {
  const res = await fetch(`${API_BASE}/api/tasks/stats`, { headers: authHeaders() });
  return res.json();
}
