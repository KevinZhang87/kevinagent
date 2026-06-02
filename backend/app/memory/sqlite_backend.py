"""
SQLite-based long-term memory backend.

Wraps the existing SQLAlchemy Memory model, preserving the original
keyword-ILIKE search logic. This is the default backend and requires
no external services.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, desc, or_, func as sql_func, delete as sql_delete

from .base import BaseMemoryBackend
from app.models.database import Memory, async_session

logger = logging.getLogger("kevin_agent.memory.sqlite")


class SqliteMemoryBackend(BaseMemoryBackend):
    """Long-term memory stored in the existing SQLite/SQLAlchemy Memory table."""

    def __init__(self, session_id: str, tenant_id: Optional[str] = None):
        super().__init__(session_id, tenant_id)

    async def save_memory(self, content: str, importance: float = 0.5, memory_type: str = "general") -> None:
        async with async_session() as session:
            mem = Memory(
                session_id=self.session_id,
                tenant_id=self.tenant_id or "default",
                content=content,
                importance=importance,
                memory_type=memory_type,
            )
            session.add(mem)
            await session.commit()
            logger.info("Memory saved: type=%s importance=%.1f len=%d", memory_type, importance, len(content))

    async def get_relevant_memories(self, query: str = "", limit: int = 5) -> list[dict]:
        async with async_session() as session:
            # Search ALL sessions for this tenant (not just current session)
            # so user preferences and role settings persist across sessions
            stmt = select(Memory)
            if self.tenant_id:
                stmt = stmt.where(Memory.tenant_id == self.tenant_id)
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
        async with async_session() as session:
            q = select(Memory).order_by(desc(Memory.importance))
            if self.tenant_id:
                q = q.where(Memory.tenant_id == self.tenant_id)
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
        async with async_session() as session:
            base_filter = Memory.tenant_id == self.tenant_id if self.tenant_id else True

            count_result = await session.execute(select(sql_func.count(Memory.id)).where(base_filter))
            total = count_result.scalar() or 0

            type_result = await session.execute(
                select(Memory.memory_type, sql_func.count(Memory.id), sql_func.avg(Memory.importance))
                .where(base_filter)
                .group_by(Memory.memory_type)
            )
            by_type = {row[0]: {"count": row[1], "avg_importance": round(row[2] or 0, 2)} for row in type_result}

            session_result = await session.execute(
                select(sql_func.count(sql_func.distinct(Memory.session_id))).where(base_filter)
            )
            session_count = session_result.scalar() or 0

            return {"total": total, "by_type": by_type, "sessions_with_memories": session_count}

    async def delete_memory(self, memory_id) -> bool:
        async with async_session() as session:
            stmt = sql_delete(Memory).where(Memory.id == memory_id)
            if self.tenant_id:
                stmt = stmt.where(Memory.tenant_id == self.tenant_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def update_memory(self, memory_id, content: str = None, importance: float = None, memory_type: str = None) -> bool:
        async with async_session() as session:
            stmt = select(Memory).where(Memory.id == memory_id)
            if self.tenant_id:
                stmt = stmt.where(Memory.tenant_id == self.tenant_id)
            result = await session.execute(stmt)
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

    async def cleanup_memories(self, max_age_days: int = 30, min_importance: float = 0.3, dry_run: bool = False) -> list:
        async with async_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=max_age_days)
            q = select(Memory).where(
                Memory.importance < min_importance,
                Memory.created_at < cutoff,
            )
            if self.tenant_id:
                q = q.where(Memory.tenant_id == self.tenant_id)
            result = await session.execute(q)
            to_delete = [m.id for m in result.scalars()]
            if to_delete and not dry_run:
                await session.execute(sql_delete(Memory).where(Memory.id.in_(to_delete)))
                await session.commit()
                logger.info("Cleaned up %d old memories (max_age=%dd, min_importance=%.1f)", len(to_delete), max_age_days, min_importance)
            return to_delete
