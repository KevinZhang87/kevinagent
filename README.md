# KevinAgent

Self-evolving AI Agent Framework with visual collaboration UI, inspired by [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) and [Tencent Marvis](https://marvis.qq.com/).

## Feature Overview

### Core Capabilities
- **Self-Evolution**: Agents automatically create and improve skills from experience
- **Multi-Model Support**: OpenAI, Anthropic, DeepSeek, Moonshot, GLM (智谱), Xiaomi MiMo (小米), Ollama (local)
- **Custom Model Configuration**: Add any model to any provider via the Settings page
- **Visual Collaboration**: Real-time agent workflow visualization with React Flow
- **Marvis-Style UI**: Dark theme with glassmorphism, smooth animations, modern design
- **Tool System**: Shell execution, file I/O, web search, Python code execution, memory storage
- **Persistent Memory**: SQLite-based conversation and long-term memory
- **WebSocket Real-time**: Live agent status updates and streaming responses
- **Chat History**: Browse and switch between past conversations
- **Skill Management**: Create, edit, enable/disable, delete, and evolve skills
- **Structured Logging**: Comprehensive logging for debugging and monitoring

### Feature Checklist

| Feature | Status | Description |
|---------|--------|-------------|
| Chat with streaming | ✅ | SSE-based streaming responses with tool call visualization |
| Multi-provider support | ✅ | 7 LLM providers: OpenAI, Anthropic, DeepSeek, Moonshot, GLM, MiMo, Ollama |
| Custom model configuration | ✅ | Add/remove custom models for any provider via Settings |
| Settings save & reload | ✅ | Hot-reload configuration without server restart |
| Chat history | ✅ | Browse, switch, and delete past conversations |
| Workflow visualization | ✅ | React Flow with real-time agent status, node creation/deletion |
| Agent management | ✅ | Create sub-agents, view status, delete agents |
| Skill auto-creation | ✅ | Skills automatically created from complex conversations |
| Skill manual creation | ✅ | Create skills via the Skills page UI |
| Skill editing | ✅ | Edit skill instructions, version auto-incremented |
| Skill toggle | ✅ | Enable/disable individual skills |
| Skill deletion | ✅ | Soft-delete (deactivate) skills |
| Skill evolution | ✅ | LLM-powered automatic skill improvement based on failure patterns |
| Tool execution | ✅ | 6 built-in tools: shell, file_read, file_write, web_search, python_exec, memory_save |
| Persistent memory | ✅ | Long-term memory with importance scoring |
| Real-time updates | ✅ | WebSocket-based agent status updates |
| Structured logging | ✅ | Timestamped logs with module names and severity levels |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### Setup

```bash
# 1. Clone and enter the project
cd kevinagent

# 2. Install backend dependencies
cd backend
pip install -r requirements.txt
cp .env.example .env  # Edit .env with your API keys

# 3. Install frontend dependencies
cd ../frontend
npm install

# 4. Start backend (Terminal 1)
cd ../backend
python run.py

# 5. Start frontend (Terminal 2)
cd ../frontend
npm run dev
```

Or use the one-click scripts:
- Windows: `start.bat`
- Linux/Mac: `bash start.sh`

### Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Architecture

```
backend/          Python FastAPI server
  app/
    core/         Agent engine, memory system
    llm/          Multi-provider LLM adapters (OpenAI, Anthropic, Ollama)
    skills/       Self-evolving skill system (manager + evolver)
    tools/        Built-in tool registry (6 tools)
    api/          REST API routes (chat, agents, skills, models)
    websocket/    Real-time WebSocket handler
    models/       SQLAlchemy ORM + Pydantic schemas
    config.py     Configuration system (YAML + env + .env)

frontend/         Next.js 15 + React 19
  src/
    app/          Pages (chat, workflow, skills, settings)
    components/   UI components (Marvis-style dark theme)
    hooks/        WebSocket hook
    lib/          API client (SSE stream + REST)
```

### Data Flow

```
User Input → Chat Page → SSE POST /api/chat
  → Agent.chat() loop:
    1. Save user message to memory
    2. Load conversation history + relevant memories + skill context
    3. Call LLM with tool schemas
    4. Execute tool calls → yield StreamChunks
    5. Repeat until no more tool calls
    6. Maybe auto-create skill from complex conversation
  → Stream SSE chunks back to frontend
  → WebSocket broadcasts agent status updates
```

## Configuration

### Environment Variables

Edit `backend/.env` with your API keys:

```env
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx
MOONSHOT_API_KEY=sk-xxx
GLM_API_KEY=xxx
MIMO_API_KEY=xxx
DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4o
MAX_ITERATIONS=30
```

### YAML Configuration Files

| File | Purpose |
|------|---------|
| `backend/config/app.yaml` | Server, database, agent parameters, active providers |
| `backend/config/providers.yaml` | LLM provider definitions, models, base URLs, defaults |
| `backend/config/tools.yaml` | Tool settings (timeouts, limits) and skill auto-creation config |

### Supported Providers

| Provider | Models | API Key Required |
|----------|--------|------------------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, o1-preview, o1-mini | Yes |
| DeepSeek | deepseek-chat, deepseek-reasoner | Yes |
| Moonshot (月之暗面) | moonshot-v1-8k/32k/128k | Yes |
| GLM (智谱) | glm-4, glm-4-flash, glm-4v | Yes |
| Xiaomi MiMo (小米) | mimo-v2.5-pro, mimo-v2.5-flash, mimo-v2-pro | Yes |
| Anthropic | claude-sonnet-4, claude-haiku-4-5, claude-opus-4 | Yes |
| Ollama (本地) | llama3.1, qwen2.5, mistral, codellama | No |

## API Endpoints

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message (SSE stream) |
| POST | `/api/chat/sessions` | Create new chat session |
| GET | `/api/chat/sessions` | List all chat sessions |
| GET | `/api/chat/sessions/{id}/messages` | Get messages for a session |
| DELETE | `/api/chat/sessions/{id}` | Delete a session |
| WS | `/api/chat/ws` | WebSocket for real-time updates |

### Agents
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| POST | `/api/agents` | Create a sub-agent |
| GET | `/api/agents/{id}` | Get agent details |
| DELETE | `/api/agents/{id}` | Delete an agent |
| GET | `/api/agents/workflow` | Get workflow graph data |

### Skills
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills` | List all skills |
| POST | `/api/skills` | Create a new skill |
| GET | `/api/skills/{name}` | Get skill details |
| PUT | `/api/skills/{name}` | Update skill (instruction, is_active) |
| DELETE | `/api/skills/{name}` | Delete (deactivate) a skill |
| POST | `/api/skills/evolve` | Trigger auto-evolution |

### Models & Settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/models/providers` | List all LLM providers |
| GET | `/api/models/providers/{id}/models` | List provider models |
| POST | `/api/models/providers/{id}/models` | Add custom model |
| DELETE | `/api/models/providers/{id}/models/{model_id}` | Remove custom model |
| GET | `/api/models/current` | Get current configuration |
| POST | `/api/models/settings/save` | Save settings & hot-reload |

## Skill System

Skills are reusable task patterns that the agent learns from experience:

1. **Auto-Creation**: When a conversation involves 4+ messages and 2+ tool calls, the agent may auto-create a skill
2. **Manual Creation**: Create skills via the Skills page with name, description, and instruction
3. **Evolution**: Skills with high failure rates (>3 failures, failures > successes) are automatically improved by the LLM
4. **Context Injection**: Relevant skills are injected into the agent's system prompt based on keyword matching

## Tool System

| Tool | Description | Security |
|------|-------------|----------|
| `shell` | Execute shell commands | 30s timeout, output truncated to 5000 chars |
| `file_read` | Read file contents | Max 50KB per read |
| `file_write` | Write to files | Max 100KB, blocked paths (/etc, /sys, C:\Windows) |
| `web_search` | DuckDuckGo search | 10s timeout, top 5 results |
| `python_exec` | Execute Python code | 30s timeout, output truncated |
| `memory_save` | Save long-term memory | Importance score 0-1 |

## Deployment

See `deploy/` directory for Docker, Kubernetes, and Helm configurations.

## License

MIT
