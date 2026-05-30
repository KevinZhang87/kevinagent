import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.memory import MemoryManager
from app.models.database import async_session, Memory
from sqlalchemy import select, func

logger = logging.getLogger("kevin_agent.memory_api")

router = APIRouter(prefix="/api/memories", tags=["memories"])


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    importance: Optional[float] = None
    memory_type: Optional[str] = None


class MemoryCleanupRequest(BaseModel):
    max_age_days: int = 30
    min_importance: float = 0.3
    dry_run: bool = False


@router.get("")
async def list_memories(session_id: Optional[str] = None, memory_type: Optional[str] = None, limit: int = 200):
    """List all memories with optional filtering."""
    mm = MemoryManager(session_id or "global")
    memories = await mm.get_all_memories(session_id=session_id, memory_type=memory_type, limit=limit)
    return {"memories": memories}


@router.get("/stats")
async def memory_stats():
    """Get memory statistics."""
    async with async_session() as session:
        total_result = await session.execute(select(func.count(Memory.id)))
        total = total_result.scalar() or 0

        type_result = await session.execute(
            select(Memory.memory_type, func.count(Memory.id), func.avg(Memory.importance))
            .group_by(Memory.memory_type)
        )
        by_type = {row[0]: {"count": row[1], "avg_importance": round(row[2] or 0, 2)} for row in type_result}

        session_result = await session.execute(select(func.count(func.distinct(Memory.session_id))))
        session_count = session_result.scalar() or 0

        # Recent count (last 24h)
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_result = await session.execute(
            select(func.count(Memory.id)).where(Memory.created_at >= recent_cutoff)
        )
        recent_24h = recent_result.scalar() or 0

    return {
        "total": total,
        "by_type": by_type,
        "sessions_with_memories": session_count,
        "recent_24h": recent_24h,
    }


@router.put("/{memory_id}")
async def update_memory(memory_id: int, request: MemoryUpdateRequest):
    """Update a specific memory."""
    mm = MemoryManager("global")
    success = await mm.update_memory(
        memory_id=memory_id,
        content=request.content,
        importance=request.importance,
        memory_type=request.memory_type,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "updated"}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int):
    """Delete a specific memory."""
    mm = MemoryManager("global")
    success = await mm.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


@router.post("/cleanup")
async def cleanup_memories(request: MemoryCleanupRequest):
    """Auto-cleanup old, low-importance memories."""
    mm = MemoryManager("global")
    deleted_ids = await mm.cleanup_memories(
        max_age_days=request.max_age_days,
        min_importance=request.min_importance,
        dry_run=request.dry_run,
    )
    return {
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "dry_run": request.dry_run,
    }
