import json
import uuid
import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Optional, Callable, Awaitable
from datetime import datetime, timedelta

from app.llm.base import BaseLLMProvider, LLMMessage
from app.llm.registry import get_provider
from app.core.memory import MemoryManager
from app.tools.registry import tool_registry, ToolResult
from app.models.database import AgentState, TokenUsage, UserSettings, async_session
from app.models.schemas import StreamChunk
import app.config as cfg

logger = logging.getLogger("kevin_agent.agent")


def _build_system_prompt() -> str:
    """Build system prompt with agent routing info from agent_config.json."""
    base = cfg.app_config.agent.system_prompt or """You are KevinAgent, the MAIN ORCHESTRATOR of a multi-agent system.

## Your Role: Orchestrator & Coordinator
You are NOT a general-purpose assistant. You are the COORDINATOR of a team of specialized agents.
Your PRIMARY job is to:
1. Understand the user's intent
2. Break complex tasks into sub-tasks
3. Delegate each sub-task to the RIGHT specialist agent using call_agent
4. Coordinate results and present a unified answer

## Critical Delegation Rules
- **ALWAYS delegate** when a task matches a sub-agent's specialty. Do NOT do their work yourself.
- **You can issue multiple call_agent calls in one response** for parallel sub-tasks.
- **For research tasks**: delegate to research_agent
- **For coding tasks**: delegate to code_agent
- **For data/Excel tasks**: delegate to data_agent
- **For tasks that don't match any specialist**: handle directly using your own tools (shell, python_exec, file_read, file_write, web_search)

## How to Delegate
1. First, use list_agents to see available agents
2. Then, use call_agent(agent_id, message) to delegate
3. The message should be a clear, complete task description with all context

## Example: How to Handle a Multi-Part Request
User: "帮我搜索最新的AI论文，然后写一个Python脚本分析它们，最后生成报告"

You should do this:
- Step 1: call_agent(research_agent, "搜索2024年最新的AI论文，重点关注LLM和Agent方向，列出top 10论文的标题、作者、摘要")
- Step 2: call_agent(code_agent, "编写Python脚本读取research_agent的输出，提取关键词并生成词频统计")
- Step 3: call_agent(data_agent, "基于分析结果生成可视化报告，包含图表和总结")

You do NOT do these tasks yourself. You DELEGATE to specialists.

## Important Rules
1. **Always answer the LATEST user message.** Focus on what the user just asked, not earlier topics.
2. **Think step by step.** Break complex problems into clear steps before acting.
3. **When in doubt, delegate.** It's better to over-delegate than to under-delegate.
4. **NEVER do a specialist's work yourself.** If a sub-agent can do it, delegate.

## File System
- Your sandbox: isolated workspace for your own files (sandbox/)
- Shared workspace: shared across all agents (shared_workspace/)
  - Use shared_read/shared_write/shared_list to collaborate with other agents
  - Put files here when other agents need access
"""

    # Load agent_config.json and append routing guidance
    try:
        config_path = Path(__file__).parent.parent.parent / "agent_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                agent_cfg = json.load(f)
            agents = agent_cfg.get("agents", {})
            if agents:
                routing_lines = ["\n## Your Team of Specialists (ALWAYS delegate to them):"]
                for agent_id, agent_item in agents.items():
                    desc = agent_item.get("description", "")
                    caps = ", ".join(agent_item.get("capabilities", []))
                    routing_lines.append(f"- **{agent_id}**: {desc}. Capabilities: {caps}")
                routing_lines.append("\n## Delegation Checklist (MUST follow):")
                routing_lines.append("1. Before doing ANY work, check if a sub-agent can handle it better")
                routing_lines.append("2. If yes, use call_agent(agent_id, message) to delegate")
                routing_lines.append("3. You can call MULTIPLE agents in ONE response for parallel work")
                routing_lines.append("4. After agents finish, synthesize their results into a unified answer")
                routing_lines.append("5. ONLY handle tasks directly when NO sub-agent is suitable")
                base += "\n".join(routing_lines)
    except Exception:
        pass

    return base


SYSTEM_PROMPT = _build_system_prompt()


# Tool subsets for different agent types.
# Sub-agents only get tools relevant to their role, saving ~50% tool schema tokens.
_AGENT_TOOL_WHITELIST: dict[str, set[str]] = {
    "research_agent": {"web_search", "file_read", "file_write", "shared_read", "shared_write", "shared_list"},
    "code_agent": {"shell", "python_exec", "file_read", "file_write", "shared_read", "shared_write", "shared_list"},
    "data_agent": {"python_exec", "file_read", "file_write", "shared_read", "shared_write", "shared_list"},
}


def _get_agent_tools(agent_id: str) -> list[dict] | None:
    """Get the appropriate tool set for an agent.

    - 'main' orchestrator: all tools (12 tools, ~1400 tokens)
    - sub-agents: filtered subset from agent_config.json or built-in whitelist
    - unknown agents: all tools (safe fallback)

    Each agent in agent_config.json can specify a "tools" list to override
    the default tool set, e.g.:
        "tools": ["web_search", "file_read", "shared_write"]

    Returns None if no tools should be used.
    """
    if agent_id == "main":
        return tool_registry.get_all_schemas()

    # Check agent_config.json for per-agent tool whitelist
    whitelist = _AGENT_TOOL_WHITELIST.get(agent_id)
    try:
        config_path = Path(__file__).parent.parent.parent / "agent_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            agent_cfg = cfg.get("agents", {}).get(agent_id, {})
            if "tools" in agent_cfg:
                whitelist = set(agent_cfg["tools"])
    except Exception:
        pass

    if whitelist is not None:
        return [t for t in tool_registry.get_all_schemas() if t["name"] in whitelist]

    # Unknown agent: give all tools (safe fallback)
    return tool_registry.get_all_schemas()


class Agent:
    """Core agent loop - handles conversation, tool calls, and self-evolution."""

    def __init__(
        self,
        agent_id: str = "main",
        provider: str = "",
        model: str = "",
        api_key: str = "",
        session_id: str = "",
        on_status_change: Optional[Callable[[str, str], Awaitable[None]]] = None,
        system_prompt: str = "",
    ):
        self.agent_id = agent_id
        self.provider_name = provider or cfg.default_provider
        self.model = model or cfg.default_model
        self.session_id = session_id or str(uuid.uuid4())
        self.llm: BaseLLMProvider = get_provider(provider, model, api_key)
        self.memory = MemoryManager(self.session_id)
        self.on_status_change = on_status_change
        self.system_prompt = system_prompt  # Agent-specific system prompt
        self.status = "idle"
        self.current_task = ""
        self.max_iterations = cfg.app_config.agent.max_iterations
        self.context_window_size = cfg.app_config.agent.context_window_size
        self.context_compression_enabled = cfg.app_config.agent.context_compression_enabled
        self.context_compression_threshold = cfg.app_config.agent.context_compression_threshold
        self.context_max_messages = cfg.app_config.agent.context_max_messages
        # Cache for skill context to avoid repeated DB queries within same session
        self._skill_context_cache: Optional[str] = None
        self.last_context_usage: dict = {}
        logger.info("Agent created: id=%s provider=%s model=%s session=%s", agent_id, provider, model, self.session_id[:8])

    async def _update_status(self, status: str, task: str = ""):
        self.status = status
        self.current_task = task
        # Debounce DB writes - only write for significant status changes
        if status in ("thinking", "executing", "idle", "error"):
            try:
                await asyncio.wait_for(self._save_status_to_db(status, task), timeout=5)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("Failed to update agent status in DB: %s", e)
        # Notify listeners
        if self.on_status_change:
            try:
                await self.on_status_change(self.agent_id, status)
            except Exception:
                pass

    async def _save_status_to_db(self, status: str, task: str):
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == self.agent_id)
            )
            state = result.scalar_one_or_none()
            if state:
                state.status = status
                state.current_task = task
                state.updated_at = datetime.utcnow()
            else:
                state = AgentState(
                    agent_id=self.agent_id,
                    status=status,
                    current_task=task,
                    model=self.model,
                    provider=self.provider_name,
                )
                session.add(state)
            await session.commit()

    def _estimate_tokens(self, messages: list[LLMMessage]) -> int:
        """Rough token estimation: ~4 chars per token for English, ~2 for CJK."""
        total_chars = 0
        for msg in messages:
            total_chars += len(msg.content)
            if msg.tool_calls:
                total_chars += len(json.dumps(msg.tool_calls))
        # Conservative estimate: ~3.5 chars per token
        return max(1, total_chars // 3)

    async def _compress_context(self, messages: list[LLMMessage], system_msg: LLMMessage) -> list[LLMMessage]:
        """Compress conversation context by summarizing older messages when approaching context window limit."""
        estimated_tokens = self._estimate_tokens(messages) + self._estimate_tokens([system_msg])
        threshold_tokens = int(self.context_window_size * self.context_compression_threshold)

        if estimated_tokens < threshold_tokens:
            return messages

        logger.info("Context compression triggered: estimated=%d tokens, threshold=%d, window=%d",
                     estimated_tokens, threshold_tokens, self.context_window_size)

        # Strategy: keep the latest ~60% of messages and summarize the rest
        total = len(messages)
        keep_recent = max(2, int(total * 0.6))
        older_messages = messages[:total - keep_recent]
        recent_messages = messages[total - keep_recent:]

        if not older_messages:
            return messages

        # Summarize older messages using LLM
        try:
            summary_text = "\n".join(
                f"[{m.role}]: {m.content[:300]}" for m in older_messages[-10:]  # Last 10 older messages
            )
            summary_prompt = f"""Summarize the following conversation context concisely. Preserve key facts, decisions, and results.
Keep the summary under 500 tokens. Focus on information that would be needed to continue the conversation.

Conversation to summarize:
{summary_text}"""
            llm = get_provider(self.provider_name, self.model)
            response = await asyncio.wait_for(
                llm.chat([LLMMessage(role="system", content="You are a conversation summarizer."),
                          LLMMessage(role="user", content=summary_prompt)]),
                timeout=30
            )
            summary = response.content.strip()
            if summary:
                # Save summary to memory
                await self.memory.save_memory(
                    content=f"[Context Summary] {summary[:500]}",
                    importance=0.7,
                    memory_type="context_summary",
                )
                # Return summary as a single user message + recent messages
                compressed = [LLMMessage(
                    role="user",
                    content=f"[Previous conversation summary]\n{summary}\n[End of summary - continuing with recent messages]"
                )]
                compressed.extend(recent_messages)
                logger.info("Context compressed: %d messages -> %d messages (summary saved)", total, len(compressed))
                return compressed
        except Exception as e:
            logger.warning("Context compression failed: %s, keeping original messages", e)

        return messages

    def _trim_message_count(self, messages: list[LLMMessage]) -> list[LLMMessage]:
        """Keep only the most recent messages within the configured cap."""
        if self.context_max_messages <= 0 or len(messages) <= self.context_max_messages:
            return messages

        trimmed = messages[-self.context_max_messages:]
        logger.debug("Context message cap applied: %d -> %d", len(messages), len(trimmed))
        return trimmed

    async def _get_context_usage(self, messages: list[LLMMessage], system_msg: LLMMessage) -> dict:
        """Get current context usage statistics."""
        estimated_tokens = self._estimate_tokens(messages) + self._estimate_tokens([system_msg])
        window_size = self.context_window_size
        usage_pct = min(100.0, (estimated_tokens / window_size) * 100) if window_size > 0 else 0
        return {
            "estimated_tokens": estimated_tokens,
            "context_window": window_size,
            "usage_percent": round(usage_pct, 1),
            "message_count": len(messages),
            "max_messages": self.context_max_messages,
            "compression_enabled": self.context_compression_enabled,
            "compression_threshold": self.context_compression_threshold,
        }

    async def _get_user_settings_map(self) -> dict[str, str]:
        async with async_session() as session:
            from sqlalchemy import select

            result = await session.execute(select(UserSettings))
            return {item.key: item.value for item in result.scalars()}

    async def _save_user_setting(self, key: str, value: str):
        async with async_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(UserSettings).where(UserSettings.key == key)
            )
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                session.add(UserSettings(key=key, value=value))
            await session.commit()

    async def _maintain_memories_if_needed(self):
        """Periodically clean low-value memories based on user settings."""
        try:
            settings = await self._get_user_settings_map()
            if str(settings.get("memory_auto_cleanup_enabled", "false")).lower() not in {"1", "true", "yes", "on"}:
                return

            interval_hours = max(1, int(settings.get("memory_cleanup_interval_hours", "12")))
            max_age_days = max(1, int(settings.get("memory_cleanup_max_age_days", "30")))
            min_importance = min(max(float(settings.get("memory_cleanup_min_importance", "0.3")), 0.0), 1.0)

            last_cleanup_at = settings.get("memory_last_cleanup_at", "")
            now = datetime.utcnow()
            if last_cleanup_at:
                try:
                    if now - datetime.fromisoformat(last_cleanup_at) < timedelta(hours=interval_hours):
                        return
                except ValueError:
                    pass

            deleted_ids = await self.memory.cleanup_memories(
                max_age_days=max_age_days,
                min_importance=min_importance,
                dry_run=False,
            )
            await self._save_user_setting("memory_last_cleanup_at", now.isoformat())

            if deleted_ids:
                logger.info("Auto memory maintenance cleaned %d memories", len(deleted_ids))
        except Exception as e:
            logger.debug("Auto memory maintenance skipped: %s", e)

    async def chat(self, user_message: str, attachments: list[dict] = None, session_id: str = None) -> AsyncIterator[StreamChunk]:
        """Process a user message and yield streaming responses.

        Args:
            user_message: The user's text message
            attachments: List of attachment dicts with keys:
                - type: "image" | "file" | "audio"
                - name: filename
                - content: base64 encoded content (for images/audio) or text content (for files)
                - mime_type: MIME type
            session_id: Optional session ID override (used for task execution to avoid polluting user chat)
        """
        logger.info("Chat request: agent=%s message_len=%d attachments=%d",
                     self.agent_id, len(user_message), len(attachments or []))
        await self._update_status("thinking", user_message[:100])

        # Use temporary memory manager if session_id is overridden (for task execution)
        from app.core.memory import MemoryManager
        original_memory = self.memory
        if session_id and session_id != self.session_id:
            self.memory = MemoryManager(session_id)

        # Build enriched message with attachment context
        enriched_message = user_message
        if attachments:
            parts = [user_message] if user_message else []
            for att in attachments:
                att_type = att.get("type", "file")
                att_name = att.get("name", "unknown")
                if att_type == "image":
                    parts.append(f"\n[Image: {att_name}]")
                elif att_type == "audio":
                    # Transcription placeholder - audio content is passed to multimodal models
                    parts.append(f"\n[Audio: {att_name}]")
                elif att_type == "file":
                    content = att.get("content", "")
                    if content:
                        parts.append(f"\n[File: {att_name}]\n{content[:10000]}")
                    else:
                        parts.append(f"\n[File: {att_name}]")
            enriched_message = "\n".join(parts)

        # Save user message FIRST, then fetch history in parallel
        await self.memory.add_message("user", enriched_message, agent_id=self.agent_id)

        # Now fetch history and other context in parallel
        conv_task = asyncio.create_task(
            self.memory.create_or_update_conversation(
                title=user_message[:50] if len(user_message) > 50 else user_message,
                model=self.model,
                provider=self.provider_name,
            )
        )
        history_task = asyncio.create_task(
            self.memory.get_messages(limit=max(self.context_max_messages, 5))
        )
        memory_task = asyncio.create_task(self.memory.get_relevant_memories(query=user_message, limit=5))

        # Wait for remaining tasks
        await asyncio.gather(conv_task, history_task, memory_task)

        messages = history_task.result()
        memories = memory_task.result()

        # Build memory context
        memory_context = ""
        if memories:
            # Limit each memory to 100 chars and total context to 500 chars
            memory_lines = []
            total_len = 0
            for m in memories:
                content = m['content'][:100]
                if total_len + len(content) > 500:
                    break
                memory_lines.append(f"- {content}")
                total_len += len(content)
            if memory_lines:
                memory_context = "\n\nRelevant memories:\n" + "\n".join(memory_lines)

        # Get skill context (with caching, limit to 300 chars)
        skill_context = self._skill_context_cache or ""
        matched_skill_names: list[str] = []
        if not skill_context:
            try:
                from app.skills.manager import SkillManager
                sm = SkillManager(agent_id=self.agent_id)
                skill_context, matched_skill_names = await sm.get_skill_context(user_message)
                if skill_context and len(skill_context) > 300:
                    skill_context = skill_context[:300] + "..."
                self._skill_context_cache = skill_context
                self._matched_skill_names = matched_skill_names
            except Exception as e:
                logger.debug("Failed to get skill context: %s", e)
        else:
            matched_skill_names = getattr(self, "_matched_skill_names", [])

        # Build LLM messages
        # Use agent-specific system prompt if available, otherwise use global prompt
        effective_prompt = self.system_prompt if self.system_prompt else SYSTEM_PROMPT
        # OPTIMIZATION: Keep system prompt static for prompt caching.
        # Dynamic context (memories, skills) goes into a separate user message
        # so the system prompt stays identical across requests.
        llm_messages = [LLMMessage(role="system", content=effective_prompt)]
        dynamic_context = (memory_context + skill_context).strip()
        if dynamic_context:
            llm_messages.append(LLMMessage(
                role="user",
                content=f"[Context]\n{dynamic_context}\n[/Context]",
            ))

        # Build multimodal content for user messages with images
        for msg in messages:
            role = msg["role"]
            if role == "tool":
                llm_messages.append(LLMMessage(
                    role="tool",
                    content=msg["content"],
                    tool_call_id=msg.get("tool_call_id", ""),
                ))
            elif role == "assistant" and msg.get("tool_calls"):
                llm_messages.append(LLMMessage(
                    role="assistant",
                    content=msg.get("content", ""),
                    tool_calls=msg["tool_calls"],
                ))
            else:
                llm_messages.append(LLMMessage(role=role, content=msg["content"]))

        # Add image attachments as separate user messages for multimodal models
        if attachments:
            for att in attachments:
                if att.get("type") == "image" and att.get("content"):
                    # For multimodal LLMs, add image as a message
                    # This is handled by the provider's format method
                    pass  # Images are embedded in the text for now

        # Apply context compression if enabled
        # Preserve leading system/context messages, only trim/compress the conversation part
        prefix_end = 1  # system prompt is always at index 0
        if len(llm_messages) > 1 and llm_messages[1].role == "user" and llm_messages[1].content.startswith("[Context]"):
            prefix_end = 2  # skip the dynamic context message too
        prefix_msgs = llm_messages[:prefix_end]
        conversation_msgs = self._trim_message_count(llm_messages[prefix_end:])
        if self.context_compression_enabled:
            conversation_msgs = await self._compress_context(conversation_msgs, llm_messages[0])
        llm_messages = prefix_msgs + conversation_msgs

        # Yield context usage info at the start
        context_usage = await self._get_context_usage(llm_messages[1:], llm_messages[0])
        self.last_context_usage = context_usage
        yield StreamChunk(type="status", content=json.dumps(context_usage), agent_id=self.agent_id)

        # Agent loop
        iteration = 0
        full_response = ""
        streaming_msg_id = None  # ID of the assistant message being streamed
        last_error_msg = ""  # Track errors for skill usage feedback
        tool_error_count = 0  # Count of tool execution failures

        # Determine which tools this agent needs
        agent_tools = _get_agent_tools(self.agent_id)
        last_had_tool_calls = True  # Start with tools on first iteration

        while iteration < self.max_iterations:
            iteration += 1
            await self._update_status("thinking", f"Iteration {iteration}")

            # OPTIMIZATION: Only send tools on first iteration or after tool results.
            # Skip tools when the previous response was text-only (conversation ending).
            tools = agent_tools if (iteration == 1 or last_had_tool_calls) else None

            # Trim conversation while preserving system prefix and dynamic context
            prefix_end = 1  # system prompt
            if len(llm_messages) > 1 and llm_messages[1].role == "user" and llm_messages[1].content.startswith("[Context]"):
                prefix_end = 2
            llm_messages = llm_messages[:prefix_end] + self._trim_message_count(llm_messages[prefix_end:])

            try:
                logger.debug("LLM call iteration=%d messages=%d", iteration, len(llm_messages))
                response = await asyncio.wait_for(self.llm.chat(llm_messages, tools), timeout=120)
                logger.debug("LLM response: content_len=%d tool_calls=%d tokens=%d", len(response.content), len(response.tool_calls), response.total_tokens)
                # Track whether this response had tool calls (for tool-sending optimization)
                last_had_tool_calls = bool(response.tool_calls)
            except asyncio.TimeoutError:
                logger.error("LLM timeout after 120s, iteration=%d", iteration)
                last_error_msg = "LLM timeout after 120s"
                yield StreamChunk(type="error", content="LLM Error: Request timed out (120s)", agent_id=self.agent_id)
                await self._update_status("error", "timeout")
                break
            except Exception as e:
                logger.error("LLM error: %s: %s", type(e).__name__, str(e))
                last_error_msg = f"LLM error: {str(e)}"
                yield StreamChunk(type="error", content=f"LLM Error: {type(e).__name__}: {str(e)}", agent_id=self.agent_id)
                await self._update_status("error", str(e))
                break

            # Record token usage (always record, even if tokens are 0)
            try:
                await self._record_token_usage(
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    total_tokens=response.total_tokens,
                    request_type="tool_call" if response.tool_calls else "chat",
                )
                if response.cached_tokens > 0:
                    logger.info("Prompt cache hit: %d/%d tokens cached (%.0f%%)",
                               response.cached_tokens, response.prompt_tokens,
                               (response.cached_tokens / response.prompt_tokens * 100) if response.prompt_tokens > 0 else 0)
            except Exception as e:
                logger.error("Failed to record token usage: %s", e)

            # Yield text content
            if response.content:
                full_response += response.content
                yield StreamChunk(type="text", content=response.content, agent_id=self.agent_id)

                # Detect and emit task plan for main agent (first iteration only)
                if iteration == 1 and self.agent_id == "main" and not hasattr(self, '_task_plan_sent'):
                    task_plan = self._parse_task_plan(response.content)
                    if task_plan:
                        self._task_plan_sent = True
                        yield StreamChunk(
                            type="task_plan",
                            content=json.dumps({"tasks": task_plan}),
                            agent_id=self.agent_id,
                        )

                # Only save streaming message when there are NO tool_calls.
                # If tool_calls are present, the tool_calls message will be saved separately.
                # This avoids having an orphan assistant message before the tool_calls message.
                if not response.tool_calls:
                    try:
                        if streaming_msg_id is None:
                            streaming_msg_id = await self.memory.add_message_and_get_id(
                                "assistant", full_response, agent_id=self.agent_id
                            )
                        else:
                            await self.memory.update_message_content(streaming_msg_id, full_response)
                    except Exception as e:
                        logger.warning("Failed to save streaming message: %s", e)

            # Handle tool calls
            if response.tool_calls:
                await self._update_status("executing", f"Using {len(response.tool_calls)} tool(s)")

                # Add ONE assistant message with ALL tool_calls to conversation context
                # (Strict providers like DeepSeek require all tool_calls in one assistant message)
                llm_messages.append(
                    LLMMessage(role="assistant", content="", tool_calls=response.tool_calls)
                )

                # Collect results for batch DB save
                tool_results: list[tuple[dict, ToolResult, str]] = []

                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    try:
                        tool_args = json.loads(tc["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_args)[:100])

                    yield StreamChunk(
                        type="tool_call",
                        content=json.dumps({"name": tool_name, "args": tool_args}),
                        agent_id=self.agent_id,
                    )

                    # For call_agent, use progress queue to forward sub-agent activity
                    progress_queue: asyncio.Queue | None = None
                    if tool_name == "call_agent":
                        progress_queue = asyncio.Queue()

                        async def progress_callback(chunk_data):
                            await progress_queue.put(chunk_data)

                        # Start tool execution as background task
                        exec_task = asyncio.create_task(
                            tool_registry.execute(tool_name, tool_args, agent_id=self.agent_id,
                                                  on_progress=progress_callback,
                                                  caller_session_id=self.memory.session_id)
                        )
                        # Forward sub-agent progress while execution runs
                        while not exec_task.done():
                            try:
                                sub_chunk = await asyncio.wait_for(progress_queue.get(), timeout=0.3)
                                yield StreamChunk(
                                    type="sub_agent_activity",
                                    content=json.dumps(sub_chunk),
                                    agent_id=self.agent_id,
                                )
                            except asyncio.TimeoutError:
                                continue
                        # Drain remaining events
                        while not progress_queue.empty():
                            sub_chunk = progress_queue.get_nowait()
                            yield StreamChunk(
                                type="sub_agent_activity",
                                content=json.dumps(sub_chunk),
                                agent_id=self.agent_id,
                            )
                        result = exec_task.result()
                    else:
                        # Normal tool execution
                        result: ToolResult = await tool_registry.execute(tool_name, tool_args, agent_id=self.agent_id,
                                                                          caller_session_id=self.memory.session_id)

                    logger.info("Tool result: %s success=%s output_len=%d", tool_name, result.success, len(result.output))

                    # Track tool errors for skill usage feedback
                    if not result.success:
                        tool_error_count += 1
                        if not last_error_msg:
                            last_error_msg = f"Tool '{tool_name}' failed: {result.error[:200]}" if result.error else f"Tool '{tool_name}' failed"

                    # Handle memory_save tool specially
                    if tool_name == "memory_save" and result.success:
                        await self.memory.save_memory(
                            content=tool_args.get("content", ""),
                            importance=tool_args.get("importance", 0.5),
                            memory_type=tool_args.get("memory_type", "general"),
                        )

                    yield StreamChunk(
                        type="tool_result",
                        content=json.dumps({
                            "name": tool_name,
                            "success": result.success,
                            "output": result.output[:2000],
                            "error": result.error[:500] if result.error else "",
                        }),
                        agent_id=self.agent_id,
                    )

                    # Update task plan status when call_agent completes
                    if tool_name == "call_agent" and hasattr(self, '_task_plan_sent'):
                        target_agent = tool_args.get("agent_id", "")
                        yield StreamChunk(
                            type="task_plan_update",
                            content=json.dumps({
                                "agent_id": target_agent,
                                "success": result.success,
                            }),
                            agent_id=self.agent_id,
                        )

                    # Add tool result to conversation context
                    # (assistant message with ALL tool_calls was added before the loop)
                    tool_result_content = result.output if result.success else f"Error: {result.error}"
                    llm_messages.append(
                        LLMMessage(
                            role="tool",
                            content=tool_result_content,
                            tool_call_id=tc.get("id", ""),
                        )
                    )

                    # Collect for batch DB save
                    tool_results.append((tc, result, tool_result_content))

                # Batch save all tool call/result messages to DB
                # IMPORTANT: Save ONE assistant message with ALL tool_calls, then tool messages.
                # Strict providers like DeepSeek require: assistant(tool_calls=[id1,id2]) -> tool(id1) -> tool(id2)
                # Saving as separate assistant messages breaks the pairing when re-read from DB.
                if tool_results:
                    # Save ONE assistant message with ALL tool_calls
                    all_tool_calls = [tc for tc, _, _ in tool_results]
                    await self.memory.add_message(
                        "assistant", "", tool_calls=all_tool_calls, agent_id=self.agent_id,
                    )
                    # Then: save all tool result messages
                    for tc, result, tool_result_content in tool_results:
                        await self.memory.add_message(
                            "tool", tool_result_content,
                            tool_call_id=tc.get("id", ""),
                            agent_id=self.agent_id,
                        )

                # Continue the loop to get LLM response to tool results
                continue
            else:
                # No more tool calls, we're done
                break

        # Save assistant response (final update if already streaming, or new save if not)
        if full_response:
            if streaming_msg_id:
                # Final update to ensure complete response is saved
                try:
                    await self.memory.update_message_content(streaming_msg_id, full_response)
                except Exception as e:
                    logger.warning("Failed to finalize streaming message: %s", e)
            else:
                # No streaming happened (e.g., tool-only response), save directly
                await self.memory.add_message("assistant", full_response, agent_id=self.agent_id)

            # Check if we should create a skill (only for complex conversations)
            if iteration > 3 and full_response:
                asyncio.create_task(self._maybe_create_skill(full_response))

            # Record skill usage (success/fail) for the matched skills
            if matched_skill_names:
                # Skill usage is considered successful if:
                # - The agent produced a response (not just error)
                # - We didn't hit max iterations (which suggests an unresolved issue)
                # - No LLM errors occurred
                skill_success = bool(full_response and iteration < self.max_iterations and not last_error_msg.startswith("LLM"))
                asyncio.create_task(self._record_skill_usage(
                    matched_skill_names,
                    success=skill_success,
                    user_query=user_message,
                    error_msg=last_error_msg,
                ))

            # Auto-evolve skills if enabled
            if cfg.tools_config.skills.auto_evolve:
                asyncio.create_task(self._auto_evolve_if_needed())

            asyncio.create_task(self._maintain_memories_if_needed())

        logger.info("Chat complete: agent=%s iterations=%d response_len=%d", self.agent_id, iteration, len(full_response))
        await self._update_status("idle", "")
        yield StreamChunk(type="done", content="", agent_id=self.agent_id)

        # Restore original memory manager if we used a temporary one
        if session_id and session_id != self.session_id:
            self.memory = original_memory

    async def _maybe_create_skill(self, response: str):
        """Check if the conversation should be saved as a skill. Runs as background task."""
        from app.skills.manager import SkillManager
        manager = SkillManager(agent_id=self.agent_id)
        try:
            await manager.try_create_from_conversation(self.session_id, response)
        except Exception as e:
            logger.debug("Skill creation skipped: %s", e)

    async def _record_skill_usage(self, skill_names: list[str], success: bool, user_query: str = "", error_msg: str = ""):
        """Record skill usage for feedback loop. Runs as background task.

        When a skill fails, we store the user query and error context so the
        SkillEvolver can make targeted improvements based on real failure data.
        """
        try:
            from app.skills.manager import SkillManager
            sm = SkillManager(agent_id=self.agent_id)
            # Build failure context for non-successful usage
            context = None
            if not success and (user_query or error_msg):
                context = {
                    "user_query": user_query[:300],
                    "skill_output": "",
                    "error": error_msg[:200],
                }
            for name in skill_names:
                await sm.record_usage(name, success, context=context)
            logger.info("Recorded skill usage: skills=%s success=%s context=%s", skill_names, success, bool(context))
        except Exception as e:
            logger.debug("Failed to record skill usage: %s", e)

    def _parse_task_plan(self, text: str) -> list[dict] | None:
        """Parse a numbered list from LLM output as a task plan."""
        import re
        lines = text.strip().split('\n')
        tasks = []
        for line in lines:
            line = line.strip()
            # Match patterns like: 1. xxx, 1、xxx, - xxx, • xxx
            match = re.match(r'^(\d+)[.、)）]\s*(.+)', line)
            if match:
                task_desc = match.group(2).strip()
                if len(task_desc) > 5:  # Filter out very short items
                    tasks.append({
                        "id": len(tasks) + 1,
                        "description": task_desc,
                        "status": "pending",  # pending, in_progress, completed, failed
                    })
        # Only return if we found a meaningful plan (2+ tasks)
        return tasks if len(tasks) >= 2 else None

    async def _auto_evolve_if_needed(self):
        """Auto-evolve skills with poor performance. Runs as background task."""
        try:
            from app.skills.evolver import SkillEvolver
            evolver = SkillEvolver()
            await evolver.auto_evolve()
        except Exception as e:
            logger.debug("Auto-evolve check skipped: %s", e)

    async def _record_token_usage(self, prompt_tokens: int, completion_tokens: int, total_tokens: int, request_type: str = "chat"):
        """Record token usage to database."""
        try:
            async with async_session() as session:
                usage = TokenUsage(
                    session_id=self.session_id,
                    agent_id=self.agent_id,
                    model=self.model,
                    provider=self.provider_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    request_type=request_type,
                )
                session.add(usage)
                await session.commit()
                logger.info("Token usage recorded: prompt=%d completion=%d total=%d model=%s provider=%s",
                            prompt_tokens, completion_tokens, total_tokens, self.model, self.provider_name)
        except Exception as e:
            logger.error("Failed to record token usage to database: %s", e)


class AgentManager:
    """Manages multiple agents and their lifecycle."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._ws_callbacks: list[Callable] = []

    def add_ws_callback(self, callback: Callable):
        self._ws_callbacks.append(callback)

    def remove_ws_callback(self, callback: Callable):
        if callback in self._ws_callbacks:
            self._ws_callbacks.remove(callback)

    async def broadcast_agent_update(self, agent_id: str, status: str):
        for cb in self._ws_callbacks:
            try:
                await cb(agent_id, status)
            except Exception:
                pass

    async def create_agent(
        self,
        agent_id: str = "",
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: str = "",
        session_id: str = "",
        parent_agent_id: str = "",
        system_prompt: str = "",
    ) -> Agent:
        agent_id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"

        # Initialize workspace directory structure
        from app.sandbox.manager import init_agent_workspace
        init_agent_workspace(agent_id)

        agent = Agent(
            agent_id=agent_id,
            provider=provider,
            model=model,
            api_key=api_key,
            session_id=session_id,
            system_prompt=system_prompt,
            on_status_change=self.broadcast_agent_update,
        )
        self._agents[agent_id] = agent

        # Persist agent state to database (upsert to handle concurrent creation)
        try:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            async with async_session() as session:
                stmt = sqlite_insert(AgentState).values(
                    agent_id=agent_id,
                    status="idle",
                    current_task="",
                    model=model,
                    provider=provider,
                    parent_agent_id=parent_agent_id or None,
                ).on_conflict_do_update(
                    index_elements=["agent_id"],
                    set_={"model": model, "provider": provider, "status": "idle"},
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            logger.warning("Failed to persist agent state to DB: %s", e)

        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def get_main_agent(self) -> Agent:
        if "main" not in self._agents:
            raise RuntimeError("Main agent not initialized")
        return self._agents["main"]

    async def get_all_agent_states(self) -> list[dict]:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(select(AgentState))
            db_states = {a.agent_id: a for a in result.scalars()}

        states = []
        # Include all DB agents, preferring in-memory values when available
        for agent_id, a in db_states.items():
            mem_agent = self._agents.get(agent_id)
            states.append({
                "agent_id": a.agent_id,
                "status": mem_agent.status if mem_agent else a.status,
                "current_task": mem_agent.current_task if mem_agent else a.current_task,
                "model": mem_agent.model if mem_agent else a.model,
                "provider": mem_agent.provider_name if mem_agent else a.provider,
                "parent_agent_id": a.parent_agent_id,
            })

        # Include memory-only agents (not yet persisted to DB)
        for agent_id, mem_agent in self._agents.items():
            if agent_id not in db_states:
                states.append({
                    "agent_id": mem_agent.agent_id,
                    "status": mem_agent.status,
                    "current_task": mem_agent.current_task,
                    "model": mem_agent.model,
                    "provider": mem_agent.provider_name,
                    "parent_agent_id": None,
                })

        return states


# Global agent manager
agent_manager = AgentManager()
