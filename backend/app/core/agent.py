import json
import uuid
import asyncio
import logging
from typing import AsyncIterator, Optional, Callable, Awaitable
from datetime import datetime, timedelta

from app.llm.base import BaseLLMProvider, LLMMessage
from app.llm.registry import get_provider
from app.core.memory import MemoryManager
from app.tools.registry import tool_registry, ToolResult
from app.models.database import AgentState, TokenUsage, UserSettings, async_session
from app.models.schemas import StreamChunk
from app.config import app_config, tools_config

logger = logging.getLogger("kevin_agent.agent")

SYSTEM_PROMPT = app_config.agent.system_prompt or """You are KevinAgent, an intelligent and self-evolving AI assistant.

Key capabilities:
- Execute commands, read/write files, search web, run Python code
- Remember important info across conversations (memory_save)
- Create and manage agents (create_agent, list_agents, call_agent)
- Learn from experience and save successful patterns as skills

File system:
- Your sandbox: isolated workspace for your own files (sandbox/)
- Shared workspace: shared across all agents (shared_workspace/)
  - Use shared_read/shared_write/shared_list to collaborate with other agents
  - Put files here when other agents need access

Always think step by step. Use tools when needed. Be helpful, accurate, and proactive.
When asked to create an agent, use create_agent tool with specified parameters.
"""


class Agent:
    """Core agent loop - handles conversation, tool calls, and self-evolution."""

    def __init__(
        self,
        agent_id: str = "main",
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: str = "",
        session_id: str = "",
        on_status_change: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ):
        self.agent_id = agent_id
        self.provider_name = provider
        self.model = model
        self.session_id = session_id or str(uuid.uuid4())
        self.llm: BaseLLMProvider = get_provider(provider, model, api_key)
        self.memory = MemoryManager(self.session_id)
        self.on_status_change = on_status_change
        self.status = "idle"
        self.current_task = ""
        self.max_iterations = app_config.agent.max_iterations
        self.context_window_size = app_config.agent.context_window_size
        self.context_compression_enabled = app_config.agent.context_compression_enabled
        self.context_compression_threshold = app_config.agent.context_compression_threshold
        self.context_max_messages = app_config.agent.context_max_messages
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
        memory_task = asyncio.create_task(self.memory.get_relevant_memories(limit=5))

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
        if not skill_context:
            try:
                from app.skills.manager import SkillManager
                sm = SkillManager(agent_id=self.agent_id)
                skill_context = await sm.get_skill_context(user_message)
                if skill_context and len(skill_context) > 300:
                    skill_context = skill_context[:300] + "..."
                self._skill_context_cache = skill_context
            except Exception as e:
                logger.debug("Failed to get skill context: %s", e)

        # Build LLM messages
        llm_messages = [LLMMessage(role="system", content=SYSTEM_PROMPT + memory_context + skill_context)]

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
        system_msg = llm_messages[0]
        conversation_msgs = self._trim_message_count(llm_messages[1:])
        if self.context_compression_enabled:
            conversation_msgs = await self._compress_context(conversation_msgs, system_msg)
        llm_messages = [system_msg] + conversation_msgs

        # Yield context usage info at the start
        context_usage = await self._get_context_usage(llm_messages[1:], llm_messages[0])
        self.last_context_usage = context_usage
        yield StreamChunk(type="status", content=json.dumps(context_usage), agent_id=self.agent_id)

        # Agent loop
        iteration = 0
        full_response = ""
        streaming_msg_id = None  # ID of the assistant message being streamed

        while iteration < self.max_iterations:
            iteration += 1
            await self._update_status("thinking", f"Iteration {iteration}")

            # Get tool schemas (cached in registry)
            tools = tool_registry.get_all_schemas()
            llm_messages = [llm_messages[0]] + self._trim_message_count(llm_messages[1:])

            try:
                logger.debug("LLM call iteration=%d messages=%d", iteration, len(llm_messages))
                response = await asyncio.wait_for(self.llm.chat(llm_messages, tools), timeout=120)
                logger.debug("LLM response: content_len=%d tool_calls=%d tokens=%d", len(response.content), len(response.tool_calls), response.total_tokens)
            except asyncio.TimeoutError:
                logger.error("LLM timeout after 120s, iteration=%d", iteration)
                yield StreamChunk(type="error", content="LLM Error: Request timed out (120s)", agent_id=self.agent_id)
                await self._update_status("error", "timeout")
                break
            except Exception as e:
                logger.error("LLM error: %s: %s", type(e).__name__, str(e))
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

                # Save or update the assistant message incrementally
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

                    # Execute tool
                    result: ToolResult = await tool_registry.execute(tool_name, tool_args, agent_id=self.agent_id)
                    logger.info("Tool result: %s success=%s output_len=%d", tool_name, result.success, len(result.output))

                    # Handle memory_save tool specially
                    if tool_name == "memory_save" and result.success:
                        await self.memory.save_memory(
                            tool_args.get("content", ""),
                            tool_args.get("importance", 0.5),
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

                    # Add tool call and result to conversation context
                    llm_messages.append(
                        LLMMessage(role="assistant", content="", tool_calls=[tc])
                    )
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

                # Batch save all tool call/result messages to DB in parallel
                if tool_results:
                    save_tasks = []
                    for tc, result, tool_result_content in tool_results:
                        save_tasks.append(self.memory.add_message(
                            "assistant", "", tool_calls=[tc], agent_id=self.agent_id,
                        ))
                        save_tasks.append(self.memory.add_message(
                            "tool", tool_result_content,
                            tool_call_id=tc.get("id", ""),
                            agent_id=self.agent_id,
                        ))
                    await asyncio.gather(*save_tasks)

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

            # Auto-evolve skills if enabled
            if tools_config.skills.auto_evolve:
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

    async def _auto_evolve_if_needed(self):
        """Auto-evolve skills with poor performance. Runs as background task."""
        try:
            from app.skills.evolver import SkillEvolver
            from app.models.database import Skill
            from sqlalchemy import select
            # Check if any skills need evolution
            async with async_session() as session:
                threshold = tools_config.skills.evolve_threshold
                result = await session.execute(
                    select(Skill).where(
                        Skill.is_active == True,
                        Skill.fail_count > threshold,
                        Skill.fail_count > Skill.success_count,
                    )
                )
                skills_needing_evolution = result.scalars().all()
                if skills_needing_evolution:
                    logger.info("Auto-evolving %d skills", len(skills_needing_evolution))
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
                await cb({"type": "agent_update", "agent_id": agent_id, "status": status})
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
            on_status_change=self.broadcast_agent_update,
        )
        self._agents[agent_id] = agent

        # Persist agent state to database so it appears in workflow/stats
        try:
            async with async_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(AgentState).where(AgentState.agent_id == agent_id)
                )
                state = result.scalar_one_or_none()
                if not state:
                    state = AgentState(
                        agent_id=agent_id,
                        status="idle",
                        current_task="",
                        model=model,
                        provider=provider,
                        parent_agent_id=parent_agent_id or None,
                    )
                    session.add(state)
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
