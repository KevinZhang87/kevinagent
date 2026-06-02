import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.memory import get_memory_backend
from app.models.database import async_session, Memory
from sqlalchemy import select, func
from app.auth.dependencies import get_current_tenant
from app.auth.schema import TenantContext

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


def _get_backend(ctx: TenantContext):
    """Create a memory backend scoped to the current tenant."""
    return get_memory_backend(session_id="__api__", tenant_id=ctx.tenant_id)


@router.get("")
async def list_memories(session_id: Optional[str] = None, memory_type: Optional[str] = None, limit: int = 200, ctx: TenantContext = Depends(get_current_tenant)):
    """List all memories with optional filtering."""
    backend = _get_backend(ctx)
    memories = await backend.get_all_memories(session_id=session_id, memory_type=memory_type, limit=limit)
    return {"memories": memories}


@router.get("/stats")
async def memory_stats(ctx: TenantContext = Depends(get_current_tenant)):
    """Get memory statistics."""
    backend = _get_backend(ctx)
    stats = await backend.get_memory_stats()

    # Add recent_24h count (API-specific stat not in backend interface)
    async with async_session() as session:
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_result = await session.execute(
            select(func.count(Memory.id)).where(Memory.created_at >= recent_cutoff, Memory.tenant_id == ctx.tenant_id)
        )
        stats["recent_24h"] = recent_result.scalar() or 0

    return stats


@router.put("/{memory_id}")
async def update_memory(memory_id: int, request: MemoryUpdateRequest, ctx: TenantContext = Depends(get_current_tenant)):
    """Update a specific memory."""
    backend = _get_backend(ctx)
    updated = await backend.update_memory(
        memory_id,
        content=request.content,
        importance=request.importance,
        memory_type=request.memory_type,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "updated"}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int, ctx: TenantContext = Depends(get_current_tenant)):
    """Delete a specific memory."""
    backend = _get_backend(ctx)
    deleted = await backend.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


@router.post("/cleanup")
async def cleanup_memories(request: MemoryCleanupRequest, ctx: TenantContext = Depends(get_current_tenant)):
    """Auto-cleanup old, low-importance memories."""
    backend = _get_backend(ctx)
    deleted_ids = await backend.cleanup_memories(
        max_age_days=request.max_age_days,
        min_importance=request.min_importance,
        dry_run=request.dry_run,
    )
    return {
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "dry_run": request.dry_run,
    }
