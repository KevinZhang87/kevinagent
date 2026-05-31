from .base import BaseTool, ToolResult
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for all available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._sandbox_manager = None
        self._sandbox_initialized = False
        self._register_builtins()

    def _register_builtins(self):
        self.register(ShellTool(self))
        self.register(FileReadTool(self))
        self.register(FileWriteTool(self))
        self.register(WebSearchTool())
        self.register(PythonExecTool(self))
        self.register(MemorySaveTool())
        self.register(CallAgentTool())
        self.register(CreateAgentTool())
        self.register(ListAgentsTool())
        # Shared workspace tools (Blackboard pattern for inter-agent collaboration)
        self.register(SharedReadTool())
        self.register(SharedWriteTool())
        self.register(SharedListTool())

    async def _ensure_sandbox(self):
        """Ensure sandbox is initialized."""
        if self._sandbox_initialized:
            return self._sandbox_manager

        from ..sandbox.manager import get_sandbox_manager
        self._sandbox_manager = get_sandbox_manager()
        await self._sandbox_manager.initialize()
        self._sandbox_initialized = True
        logger.info(f"Sandbox backend: {self._sandbox_manager.backend_name}")
        return self._sandbox_manager

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]

    def get_all_names(self) -> list[str]:
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict, agent_id: str = None, on_progress=None, caller_session_id: str = "") -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
        try:
            # Pass caller agent_id for sandbox isolation, but avoid collision
            # with tool arguments that also use 'agent_id' (e.g. call_agent)
            kwargs = dict(arguments)
            if "agent_id" not in kwargs and agent_id:
                kwargs["agent_id"] = agent_id
            # Pass on_progress callback for tools that support streaming (e.g. call_agent)
            if on_progress:
                kwargs["on_progress"] = on_progress
            # Pass caller_session_id so child agents write to the parent's session
            if caller_session_id:
                kwargs["caller_session_id"] = caller_session_id
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


# Built-in tools
class ShellTool(BaseTool):
    name = "shell"
    description = "Execute a shell command and return the output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
        },
        "required": ["command"],
    }

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def execute(self, command: str = "", agent_id: str = None, **kwargs) -> ToolResult:
        try:
            sandbox = await self._registry._ensure_sandbox()
            result = await sandbox.execute_command(command, timeout=30, agent_id=agent_id)
            return ToolResult(
                success=result.success,
                output=result.output,
                error=result.error,
            )
        except Exception as e:
            logger.error(f"Shell tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))


class FileReadTool(BaseTool):
    name = "file_read"
    description = "Read the contents of a file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read"},
        },
        "required": ["path"],
    }

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def execute(self, path: str = "", agent_id: str = None, **kwargs) -> ToolResult:
        try:
            sandbox = await self._registry._ensure_sandbox()
            result = await sandbox.read_file(path, agent_id=agent_id)
            return ToolResult(
                success=result.success,
                output=result.output,
                error=result.error,
            )
        except Exception as e:
            logger.error(f"File read tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Write content to a file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to write"},
            "content": {"type": "string", "description": "Content to write to the file"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def execute(self, path: str = "", content: str = "", agent_id: str = None, **kwargs) -> ToolResult:
        try:
            sandbox = await self._registry._ensure_sandbox()
            result = await sandbox.write_file(path, content, agent_id=agent_id)
            return ToolResult(
                success=result.success,
                output=result.output,
                error=result.error,
            )
        except Exception as e:
            logger.error(f"File write tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web using a search engine."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    }

    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10.0,
                )
                # Simple HTML parsing for search results
                text = resp.text
                results = []
                import re
                links = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', text)
                for url, title in links[:5]:
                    title_clean = re.sub(r'<[^>]+>', '', title)
                    results.append(f"- {title_clean}: {url}")
                if results:
                    return ToolResult(success=True, output="\n".join(results))
                return ToolResult(success=True, output="No results found.")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class PythonExecTool(BaseTool):
    name = "python_exec"
    description = "Execute Python code and return the output."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
        },
        "required": ["code"],
    }

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def execute(self, code: str = "", agent_id: str = None, **kwargs) -> ToolResult:
        try:
            sandbox = await self._registry._ensure_sandbox()
            result = await sandbox.execute_python(code, timeout=30, agent_id=agent_id)
            return ToolResult(
                success=result.success,
                output=result.output,
                error=result.error,
            )
        except Exception as e:
            logger.error(f"Python exec tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))


class MemorySaveTool(BaseTool):
    name = "memory_save"
    description = "Save important information to long-term memory. Use memory_type to categorize: 'general' for facts, 'user_preference' for user preferences/likes/needs, 'skill' for learned patterns."
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The information to remember"},
            "importance": {"type": "number", "description": "Importance score 0-1", "default": 0.5},
            "memory_type": {"type": "string", "description": "Memory category: 'general', 'user_preference', 'skill', 'context_summary'", "enum": ["general", "user_preference", "skill", "context_summary"], "default": "general"},
        },
        "required": ["content"],
    }

    async def execute(self, content: str = "", importance: float = 0.5, **kwargs) -> ToolResult:
        # This is handled by the agent loop
        return ToolResult(success=True, output=f"Memory saved: {content[:100]}...")


class CallAgentTool(BaseTool):
    name = "call_agent"
    description = "Delegate a task to a specific sub-agent. Use this when the user's request involves a sub-agent's specialty area. You can issue multiple call_agent calls in one response for parallel sub-tasks. Use list_agents to see available agents first."
    parameters = {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "The exact agent ID to delegate to (e.g. 'main', 'research_agent'). Use list_agents to see available IDs."},
            "message": {"type": "string", "description": "A clear, specific task description for the sub-agent. Include all context needed."},
        },
        "required": ["agent_id", "message"],
    }

    async def execute(self, agent_id: str = "", message: str = "", on_progress=None, caller_session_id: str = "", **kwargs) -> ToolResult:
        try:
            from app.core.agent import agent_manager

            if not agent_id or not message:
                return ToolResult(success=False, output="", error="Both agent_id and message are required")

            agent = agent_manager.get_agent(agent_id)
            if not agent:
                # Try to auto-create from database
                logger.info("call_agent: agent '%s' not in memory, attempting auto-creation", agent_id)
                from app.models.database import AgentState, async_session
                from sqlalchemy import select as sel
                async with async_session() as session:
                    result = await session.execute(
                        sel(AgentState).where(AgentState.agent_id == agent_id)
                    )
                    state = result.scalar_one_or_none()
                if state:
                    agent = await agent_manager.create_agent(
                        agent_id=state.agent_id,
                        provider=state.provider,
                        model=state.model,
                        session_id=caller_session_id,  # Share parent's session
                    )
                else:
                    available = list(agent_manager._agents.keys())
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Agent '{agent_id}' not found. Available agents: {available}",
                    )

            # If sub-agent has no custom system_prompt, prepend role context to message
            effective_message = message
            if not agent.system_prompt:
                # Try to get role info from agent_config.json
                try:
                    import json
                    from pathlib import Path
                    config_path = Path(__file__).parent.parent.parent / "agent_config.json"
                    if config_path.exists():
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        agent_cfg = cfg.get("agents", {}).get(agent_id, {})
                        if agent_cfg:
                            desc = agent_cfg.get("description", "")
                            caps = ", ".join(agent_cfg.get("capabilities", []))
                            effective_message = f"[你的角色: {agent_id} - {desc}。能力: {caps}]\n\n{message}"
                except Exception:
                    pass

            # Run child agent in its OWN session to avoid polluting parent's
            # message history (mixing tool_calls from different agents breaks
            # strict providers like DeepSeek).
            import uuid
            # Include parent session prefix so we can query child sessions later
            parent_prefix = caller_session_id[:8] if caller_session_id else "unknown"
            child_session = f"child_{agent_id}_{parent_prefix}_{uuid.uuid4().hex[:6]}"
            logger.info("call_agent: delegating to '%s' (child_session=%s)", agent_id, child_session)

            # Collect full response from the target agent, forwarding intermediate chunks
            full_response = ""
            async for chunk in agent.chat(effective_message, session_id=child_session):
                if chunk.type == "text":
                    full_response += chunk.content
                # Forward intermediate progress to parent agent's stream
                if on_progress and chunk.type in ("text", "tool_call", "tool_result", "status"):
                    try:
                        await on_progress({
                            "type": chunk.type,
                            "content": chunk.content,
                            "agent_id": agent_id,
                        })
                    except Exception:
                        pass

            if not full_response:
                return ToolResult(success=True, output=f"Agent '{agent_id}' returned no text response.")

            return ToolResult(
                success=True,
                output=f"Response from agent '{agent_id}':\n{full_response}",
            )
        except Exception as e:
            logger.error("call_agent tool error: %s", e)
            return ToolResult(success=False, output="", error=str(e))


class CreateAgentTool(BaseTool):
    name = "create_agent"
    description = "Create a new sub-agent with a specific model and provider. Use this when you need a specialized agent that doesn't exist yet. After creation, use call_agent to delegate tasks to it."
    parameters = {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "Unique agent ID using ASCII characters (e.g. 'research_agent', 'data_agent'). Avoid Chinese characters."},
            "model": {"type": "string", "description": "Model name (e.g. 'gpt-4o', 'mimo-v2.5-pro'). Defaults to system default."},
            "provider": {"type": "string", "description": "Provider name (e.g. 'openai', 'mimo'). Defaults to system default."},
        },
        "required": ["agent_id"],
    }

    async def execute(self, agent_id: str = "", model: str = "", provider: str = "", **_kwargs) -> ToolResult:
        try:
            from app.core.agent import agent_manager

            if not agent_id:
                return ToolResult(success=False, output="", error="agent_id is required")

            # Check if agent already exists
            existing = agent_manager.get_agent(agent_id)
            if existing:
                return ToolResult(
                    success=True,
                    output=f"Agent '{agent_id}' already exists.",
                )

            # Limit dynamic agent creation to prevent runaway spawning
            # Count non-pre-created agents (agents not in agent_config.json)
            try:
                import json
                from pathlib import Path
                config_path = Path(__file__).parent.parent.parent / "agent_config.json"
                pre_created_ids = set()
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    pre_created_ids = set(cfg.get("agents", {}).keys())
                dynamic_count = sum(1 for aid in agent_manager._agents.keys() if aid not in pre_created_ids and aid != "main")
                if dynamic_count >= 3:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Dynamic agent limit reached (3). Existing dynamic agents: {[aid for aid in agent_manager._agents.keys() if aid not in pre_created_ids and aid != 'main']}",
                    )
            except Exception:
                pass

            # Use defaults if not specified
            if not provider:
                from app.config import default_provider
                provider = default_provider
            if not model:
                from app.config import default_model
                model = default_model

            # Create the agent
            await agent_manager.create_agent(
                agent_id=agent_id,
                provider=provider,
                model=model,
            )

            return ToolResult(
                success=True,
                output=f"Agent '{agent_id}' created successfully with provider='{provider}', model='{model}'.",
            )
        except Exception as e:
            logger.error("create_agent tool error: %s", e)
            return ToolResult(success=False, output="", error=str(e))


class ListAgentsTool(BaseTool):
    name = "list_agents"
    description = "List all available agents with their status and capabilities. Use this before call_agent to see which agents you can delegate to."
    parameters = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, **_kwargs) -> ToolResult:
        try:
            from app.core.agent import agent_manager

            agents = []
            for agent_id, agent in agent_manager._agents.items():
                agents.append({
                    "agent_id": agent_id,
                    "model": agent.model,
                    "provider": agent.provider_name,
                    "status": agent.status,
                })

            if not agents:
                return ToolResult(success=True, output="No agents currently active. Use create_agent to create one.")

            lines = [f"- {a['agent_id']} ({a['provider']}/{a['model']}) [{a['status']}]" for a in agents]
            return ToolResult(
                success=True,
                output=f"Available agents ({len(agents)}):\n" + "\n".join(lines),
            )
        except Exception as e:
            logger.error("list_agents tool error: %s", e)
            return ToolResult(success=False, output="", error=str(e))


class SharedReadTool(BaseTool):
    name = "shared_read"
    description = "Read a file from the shared workspace (accessible by all agents)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path within shared_workspace/"},
        },
        "required": ["path"],
    }

    async def execute(self, path: str = "", **_kwargs) -> ToolResult:
        try:
            from app.sandbox.manager import get_shared_workspace
            import os

            shared_dir = get_shared_workspace()
            # Prevent path traversal
            full_path = os.path.normpath(os.path.join(shared_dir, path))
            if not full_path.startswith(shared_dir):
                return ToolResult(success=False, output="", error="Path traversal not allowed")

            if not os.path.exists(full_path):
                return ToolResult(success=False, output="", error=f"File not found: {path}")

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read(100000)  # Limit to 100KB

            return ToolResult(success=True, output=content)
        except Exception as e:
            logger.error("shared_read tool error: %s", e)
            return ToolResult(success=False, output="", error=str(e))


class SharedWriteTool(BaseTool):
    name = "shared_write"
    description = "Write a file to the shared workspace (accessible by all agents)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path within shared_workspace/"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str = "", content: str = "", **_kwargs) -> ToolResult:
        try:
            from app.sandbox.manager import get_shared_workspace
            import os

            shared_dir = get_shared_workspace()
            # Prevent path traversal
            full_path = os.path.normpath(os.path.join(shared_dir, path))
            if not full_path.startswith(shared_dir):
                return ToolResult(success=False, output="", error="Path traversal not allowed")

            # Create directories if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(success=True, output=f"Written to shared:{path}")
        except Exception as e:
            logger.error("shared_write tool error: %s", e)
            return ToolResult(success=False, output="", error=str(e))


class SharedListTool(BaseTool):
    name = "shared_list"
    description = "List files in the shared workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path within shared_workspace/ (default: root)", "default": ""},
        },
    }

    async def execute(self, path: str = "", **_kwargs) -> ToolResult:
        try:
            from app.sandbox.manager import get_shared_workspace
            import os

            shared_dir = get_shared_workspace()
            target_dir = os.path.normpath(os.path.join(shared_dir, path))
            if not target_dir.startswith(shared_dir):
                return ToolResult(success=False, output="", error="Path traversal not allowed")

            if not os.path.exists(target_dir):
                return ToolResult(success=False, output="", error=f"Directory not found: {path}")

            items = []
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isdir(item_path):
                    items.append(f"📁 {item}/")
                else:
                    size = os.path.getsize(item_path)
                    items.append(f"📄 {item} ({size} bytes)")

            if not items:
                return ToolResult(success=True, output="Shared workspace is empty")

            return ToolResult(success=True, output="\n".join(items))
        except Exception as e:
            logger.error("shared_list tool error: %s", e)
            return ToolResult(success=False, output="", error=str(e))


tool_registry = ToolRegistry()
