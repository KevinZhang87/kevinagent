import json
import logging
from datetime import datetime
from sqlalchemy import select, desc, or_

from app.models.database import Memory, Message, Conversation, async_session

logger = logging.getLogger("kevin_agent.memory")


class MemoryManager:
    """Manages agent memory - short-term (conversation) and long-term (persistent)."""

    def __init__(self, session_id: str):
        self.session_id = session_id

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
        async with async_session() as session:
            mem = Memory(
                session_id=self.session_id,
                content=content,
                importance=importance,
                memory_type=memory_type,
            )
            session.add(mem)
            await session.commit()
            logger.info("Memory saved: type=%s importance=%.1f len=%d", memory_type, importance, len(content))

    async def get_relevant_memories(self, query: str = "", limit: int = 5) -> list[dict]:
        async with async_session() as session:
            stmt = select(Memory).where(Memory.session_id == self.session_id)
            # Keyword matching: split query into words and filter by LIKE
            if query and query.strip():
                keywords = [kw.strip() for kw in query.split() if len(kw.strip()) >= 2][:5]
                if keywords:
                    conditions = [Memory.content.ilike(f"%{kw}%") for kw in keywords]
                    stmt = stmt.where(or_(*conditions))
            stmt = stmt.order_by(desc(Memory.importance)).limit(limit)
            result = await session.execute(stmt)
            return [
                {
                    "id": m.id,
                    "content": m.content,
                    "importance": m.importance,
                    "type": m.memory_type,
                    "created_at": m.created_at.isoformat(),
                }
                for m in result.scalars()
            ]

    async def get_all_memories(self, session_id: str = None, memory_type: str = None, limit: int = 100) -> list[dict]:
        """Get all memories, optionally filtered by session or type."""
        async with async_session() as session:
            q = select(Memory).order_by(desc(Memory.importance))
            if session_id:
                q = q.where(Memory.session_id == session_id)
            if memory_type:
                q = q.where(Memory.memory_type == memory_type)
            q = q.limit(limit)
            result = await session.execute(q)
            return [
                {
                    "id": m.id,
                    "session_id": m.session_id,
                    "content": m.content,
                    "importance": m.importance,
                    "type": m.memory_type,
                    "created_at": m.created_at.isoformat(),
                }
                for m in result.scalars()
            ]

    async def get_memory_stats(self) -> dict:
        """Get memory statistics."""
        async with async_session() as session:
            from sqlalchemy import func as sql_func
            # Total count
            count_result = await session.execute(select(sql_func.count(Memory.id)))
            total = count_result.scalar() or 0
            # By type
            type_result = await session.execute(
                select(Memory.memory_type, sql_func.count(Memory.id), sql_func.avg(Memory.importance))
                .group_by(Memory.memory_type)
            )
            by_type = {row[0]: {"count": row[1], "avg_importance": round(row[2] or 0, 2)} for row in type_result}
            # Sessions with memories
            session_result = await session.execute(
                select(sql_func.count(sql_func.distinct(Memory.session_id)))
            )
            session_count = session_result.scalar() or 0
            return {"total": total, "by_type": by_type, "sessions_with_memories": session_count}

    async def delete_memory(self, memory_id: int) -> bool:
        """Delete a specific memory by ID."""
        async with async_session() as session:
            from sqlalchemy import delete
            result = await session.execute(delete(Memory).where(Memory.id == memory_id))
            await session.commit()
            return result.rowcount > 0

    async def update_memory(self, memory_id: int, content: str = None, importance: float = None, memory_type: str = None) -> bool:
        """Update a specific memory."""
        async with async_session() as session:
            result = await session.execute(select(Memory).where(Memory.id == memory_id))
            mem = result.scalar_one_or_none()
            if not mem:
                return False
            if content is not None:
                mem.content = content
            if importance is not None:
                mem.importance = importance
            if memory_type is not None:
                mem.memory_type = memory_type
            await session.commit()
            return True

    async def cleanup_memories(self, max_age_days: int = 30, min_importance: float = 0.3, dry_run: bool = False) -> list[int]:
        """Remove old, low-importance memories. Returns list of deleted IDs."""
        async with async_session() as session:
            from sqlalchemy import delete as sql_delete
            cutoff = datetime.utcnow() - __import__("datetime").timedelta(days=max_age_days)
            q = select(Memory).where(
                Memory.importance < min_importance,
                Memory.created_at < cutoff,
            )
            result = await session.execute(q)
            to_delete = [m.id for m in result.scalars()]
            if to_delete and not dry_run:
                await session.execute(sql_delete(Memory).where(Memory.id.in_(to_delete)))
                await session.commit()
                logger.info("Cleaned up %d old memories (max_age=%dd, min_importance=%.1f)", len(to_delete), max_age_days, min_importance)
            return to_delete

    async def create_or_update_conversation(self, title: str = "New Chat", model: str = "gpt-4o", provider: str = "openai"):
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
                    title=title,
                    model=model,
                    provider=provider,
                )
                session.add(conv)
            await session.commit()

    async def get_conversations(self) -> list[dict]:
        async with async_session() as session:
            # Exclude child sessions (child_{agent_id}_{prefix}_{uuid}) from the list
            result = await session.execute(
                select(Conversation)
                .where(~Conversation.session_id.like("child_%"))
                .order_by(desc(Conversation.updated_at))
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
