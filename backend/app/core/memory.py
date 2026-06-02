import json
import logging
from datetime import datetime
from sqlalchemy import select, desc

from app.models.database import Message, Conversation, async_session
from app.memory import get_memory_backend, BaseMemoryBackend

logger = logging.getLogger("kevin_agent.memory")


class MemoryManager:
    """Manages agent memory - short-term (conversation) and long-term (persistent).

    Long-term memory is delegated to a pluggable backend (SQLite or mem0).
    Short-term messages and conversation metadata remain in SQLite directly.
    """

    def __init__(self, session_id: str, tenant_id: str = None):
        self.session_id = session_id
        self._memory_backend: BaseMemoryBackend = get_memory_backend(session_id, tenant_id=tenant_id)

    async def add_message(self, role: str, content: str, tool_calls: list = None, tool_call_id: str = "", agent_id: str = "main"):
        async with async_session() as session:
            msg = Message(
                session_id=self.session_id,
                role=role,
                content=content,
                tool_calls=json.dumps(tool_calls) if tool_calls else None,
                tool_call_id=tool_call_id,
                agent_id=agent_id,
            )
            session.add(msg)
            await session.commit()
            logger.debug("Message saved: session=%s role=%s len=%d", self.session_id[:8], role, len(content))

    async def add_messages_batch(self, messages_data: list[dict]):
        """Save multiple messages in a single DB transaction for better performance."""
        async with async_session() as session:
            for md in messages_data:
                msg = Message(
                    session_id=self.session_id,
                    role=md["role"],
                    content=md["content"],
                    tool_calls=json.dumps(md["tool_calls"]) if md.get("tool_calls") else None,
                    tool_call_id=md.get("tool_call_id", ""),
                    agent_id=md.get("agent_id", "main"),
                )
                session.add(msg)
            await session.commit()
            logger.debug("Batch saved %d messages: session=%s", len(messages_data), self.session_id[:8])

    async def add_message_and_get_id(self, role: str, content: str, tool_calls: list = None, tool_call_id: str = "", agent_id: str = "main") -> int:
        """Add a message and return its ID for later updates."""
        async with async_session() as session:
            msg = Message(
                session_id=self.session_id,
                role=role,
                content=content,
                tool_calls=json.dumps(tool_calls) if tool_calls else None,
                tool_call_id=tool_call_id,
                agent_id=agent_id,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            logger.debug("Message saved with ID: session=%s role=%s id=%d", self.session_id[:8], role, msg.id)
            return msg.id

    async def update_message_content(self, message_id: int, content: str):
        """Update an existing message's content."""
        async with async_session() as session:
            result = await session.execute(
                select(Message).where(Message.id == message_id)
            )
            msg = result.scalar_one_or_none()
            if msg:
                msg.content = content
                await session.commit()
                logger.debug("Message updated: id=%d len=%d", message_id, len(content))

    async def get_messages(self, limit: int = 50) -> list[dict]:
        async with async_session() as session:
            # Use ID for ordering to ensure correct sequence
            # (created_at can be the same for messages saved in parallel)
            result = await session.execute(
                select(Message)
                .where(Message.session_id == self.session_id)
                .order_by(desc(Message.id))
                .limit(limit)
            )
            messages = []
            for msg in reversed(result.scalars().all()):
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": json.loads(msg.tool_calls) if msg.tool_calls else None,
                    "tool_call_id": msg.tool_call_id or "",
                })
            return messages

    async def save_memory(self, content: str, importance: float = 0.5, memory_type: str = "general"):
        await self._memory_backend.save_memory(content, importance, memory_type)

    async def get_relevant_memories(self, query: str = "", limit: int = 5) -> list[dict]:
        return await self._memory_backend.get_relevant_memories(query, limit)

    async def get_all_memories(self, session_id: str = None, memory_type: str = None, limit: int = 100) -> list[dict]:
        """Get all memories, optionally filtered by session or type."""
        return await self._memory_backend.get_all_memories(session_id, memory_type, limit)

    async def get_memory_stats(self) -> dict:
        """Get memory statistics."""
        return await self._memory_backend.get_memory_stats()

    async def delete_memory(self, memory_id: int) -> bool:
        """Delete a specific memory by ID."""
        return await self._memory_backend.delete_memory(memory_id)

    async def update_memory(self, memory_id: int, content: str = None, importance: float = None, memory_type: str = None) -> bool:
        """Update a specific memory."""
        return await self._memory_backend.update_memory(memory_id, content, importance, memory_type)

    async def cleanup_memories(self, max_age_days: int = 30, min_importance: float = 0.3, dry_run: bool = False) -> list[int]:
        """Remove old, low-importance memories. Returns list of deleted IDs."""
        return await self._memory_backend.cleanup_memories(max_age_days, min_importance, dry_run)

    async def create_or_update_conversation(self, title: str = "New Chat", model: str = "gpt-4o", provider: str = "openai", tenant_id: str = None):
        async with async_session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.session_id == self.session_id)
            )
            conv = result.scalar_one_or_none()
            if conv:
                conv.updated_at = datetime.utcnow()
            else:
                conv = Conversation(
                    session_id=self.session_id,
                    tenant_id=tenant_id or "default",
                    title=title,
                    model=model,
                    provider=provider,
                )
                session.add(conv)
            await session.commit()

    async def get_conversations(self, tenant_id: str = None) -> list[dict]:
        async with async_session() as session:
            # Exclude child sessions (child_{agent_id}_{prefix}_{uuid}) from the list
            query = (
                select(Conversation)
                .where(~Conversation.session_id.like("child_%"))
            )
            if tenant_id:
                query = query.where(Conversation.tenant_id == tenant_id)
            result = await session.execute(
                query.order_by(desc(Conversation.updated_at))
            )
            return [
                {
                    "session_id": c.session_id,
                    "title": c.title,
                    "model": c.model,
                    "provider": c.provider,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat(),
                }
                for c in result.scalars()
            ]

    async def get_conversation_messages(self, session_id: str, limit: int = 100) -> list[dict]:
        """Get messages for a specific conversation."""
        async with async_session() as session:
            result = await session.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.id)
                .limit(limit)
            )
            messages = []
            for msg in result.scalars():
                messages.append({
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": json.loads(msg.tool_calls) if msg.tool_calls else None,
                    "tool_call_id": msg.tool_call_id or "",
                    "agent_id": msg.agent_id,
                    "created_at": msg.created_at.isoformat(),
                })
            return messages

    async def delete_conversation(self, session_id: str) -> bool:
        """Delete a conversation and all its messages."""
        async with async_session() as session:
            from sqlalchemy import delete
            # Delete messages first
            await session.execute(
                delete(Message).where(Message.session_id == session_id)
            )
            # Delete conversation
            result = await session.execute(
                delete(Conversation).where(Conversation.session_id == session_id)
            )
            await session.commit()
            logger.info("Conversation deleted: %s", session_id[:8])
            return result.rowcount > 0
