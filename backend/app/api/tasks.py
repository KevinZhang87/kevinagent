import logging
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func, desc

from app.models.database import async_session, ScheduledTask, TaskExecution
from app.scheduler.engine import (
    start_task, stop_task, run_task_now, get_running_task_ids, _parse_interval,
)
from app.auth.dependencies import get_current_tenant
from app.auth.schema import TenantContext

logger = logging.getLogger("kevin_agent.tasks")

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Schemas ────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    name: str
    message: str
    interval: str = "1h"  # 30s, 10m, 2h, 1d
    agent_id: str = "main"


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    message: Optional[str] = None
    interval: Optional[str] = None
    agent_id: Optional[str] = None
    is_active: Optional[bool] = None


# ── CRUD ───────────────────────────────────────────────────────────

@router.get("")
async def list_tasks(ctx: TenantContext = Depends(get_current_tenant)):
    """List all scheduled tasks with status."""
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.tenant_id == ctx.tenant_id).order_by(ScheduledTask.created_at.desc())
        )
        tasks = result.scalars().all()
        running_ids = get_running_task_ids()
        return {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "message": t.message,
                    "interval": t.interval,
                    "agent_id": t.agent_id,
                    "is_active": t.is_active,
                    "is_running": t.task_id in running_ids,
                    "last_run": str(t.last_run) if t.last_run else None,
                    "next_run": str(t.next_run) if t.next_run else None,
                    "run_count": t.run_count,
                    "fail_count": t.fail_count,
                    "created_at": str(t.created_at),
                }
                for t in tasks
            ]
        }


@router.post("")
async def create_task(request: TaskCreate, ctx: TenantContext = Depends(get_current_tenant)):
    """Create a new scheduled task."""
    # Validate interval
    try:
        _parse_interval(request.interval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    try:
        td = _parse_interval(request.interval)
        next_run = datetime.utcnow() + td
    except Exception:
        next_run = None

    async with async_session() as session:
        task = ScheduledTask(
            task_id=task_id,
            tenant_id=ctx.tenant_id,
            name=request.name,
            message=request.message,
            interval=request.interval,
            agent_id=request.agent_id,
            next_run=next_run,
        )
        session.add(task)
        await session.commit()

    # Auto-start the task
    await start_task(task_id)

    logger.info("Scheduled task created: %s name=%s interval=%s", task_id, request.name, request.interval)
    return {"task_id": task_id, "status": "created", "is_active": True}


@router.get("/stats")
async def get_tasks_stats(ctx: TenantContext = Depends(get_current_tenant)):
    """Get overall scheduler statistics."""
    async with async_session() as session:
        total_tasks = (await session.execute(
            select(func.count(ScheduledTask.id)).where(ScheduledTask.tenant_id == ctx.tenant_id)
        )).scalar() or 0

        active_tasks = (await session.execute(
            select(func.count(ScheduledTask.id)).where(ScheduledTask.is_active == True, ScheduledTask.tenant_id == ctx.tenant_id)  # noqa: E712
        )).scalar() or 0

        # Get task IDs for this tenant to scope executions
        task_ids_result = await session.execute(
            select(ScheduledTask.task_id).where(ScheduledTask.tenant_id == ctx.tenant_id)
        )
        task_ids = [r[0] for r in task_ids_result]

        total_executions = 0
        failed_executions = 0
        recent_executions = 0
        if task_ids:
            total_executions = (await session.execute(
                select(func.count(TaskExecution.id)).where(TaskExecution.task_id.in_(task_ids))
            )).scalar() or 0

            failed_executions = (await session.execute(
                select(func.count(TaskExecution.id)).where(TaskExecution.status == "failed", TaskExecution.task_id.in_(task_ids))
            )).scalar() or 0

            # Recent executions (last 24h)
            since = datetime.utcnow() - timedelta(hours=24)
            recent_executions = (await session.execute(
                select(func.count(TaskExecution.id)).where(TaskExecution.started_at >= since, TaskExecution.task_id.in_(task_ids))
            )).scalar() or 0

    running_ids = get_running_task_ids()

    return {
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
        "running_tasks": len(running_ids),
        "total_executions": total_executions,
        "failed_executions": failed_executions,
        "recent_executions_24h": recent_executions,
    }


@router.get("/{task_id}/executions")
async def get_task_executions(task_id: str, limit: int = 20, ctx: TenantContext = Depends(get_current_tenant)):
    """Get execution history for a task."""
    async with async_session() as session:
        # Verify the task belongs to this tenant
        task_result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id, ScheduledTask.tenant_id == ctx.tenant_id)
        )
        if not task_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Task not found")

        result = await session.execute(
            select(TaskExecution)
            .where(TaskExecution.task_id == task_id)
            .order_by(desc(TaskExecution.started_at))
            .limit(limit)
        )
        executions = result.scalars().all()
        return {
            "executions": [
                {
                    "execution_id": e.execution_id,
                    "task_id": e.task_id,
                    "status": e.status,
                    "result": e.result[:2000] if e.result else "",
                    "has_more": len(e.result) > 2000 if e.result else False,
                    "started_at": str(e.started_at),
                    "finished_at": str(e.finished_at) if e.finished_at else None,
                    "duration_ms": e.duration_ms,
                }
                for e in executions
            ]
        }


@router.patch("/{task_id}")
async def update_task(task_id: str, request: TaskUpdate, ctx: TenantContext = Depends(get_current_tenant)):
    """Update a scheduled task."""
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id, ScheduledTask.tenant_id == ctx.tenant_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        was_active = task.is_active
        if request.name is not None:
            task.name = request.name
        if request.message is not None:
            task.message = request.message
        if request.interval is not None:
            try:
                _parse_interval(request.interval)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            task.interval = request.interval
        if request.agent_id is not None:
            task.agent_id = request.agent_id
        if request.is_active is not None:
            task.is_active = request.is_active

        # Recalculate next_run
        try:
            td = _parse_interval(task.interval)
            task.next_run = datetime.utcnow() + td if task.is_active else None
        except Exception:
            task.next_run = None

        await session.commit()

    # Handle start/stop
    if request.is_active is not None:
        if request.is_active and not was_active:
            await start_task(task_id)
        elif not request.is_active and was_active:
            stop_task(task_id)

    # If interval changed and task is active, restart it
    if request.interval is not None and task.is_active:
        stop_task(task_id)
        await start_task(task_id)

    logger.info("Task updated: %s", task_id)
    return {"task_id": task_id, "status": "updated"}


@router.delete("/{task_id}")
async def delete_task(task_id: str, ctx: TenantContext = Depends(get_current_tenant)):
    """Delete a scheduled task."""
    # Verify task belongs to this tenant
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id, ScheduledTask.tenant_id == ctx.tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Task not found")

    stop_task(task_id)
    async with async_session() as session:
        from sqlalchemy import delete as sql_delete
        await session.execute(sql_delete(ScheduledTask).where(ScheduledTask.task_id == task_id))
        await session.execute(sql_delete(TaskExecution).where(TaskExecution.task_id == task_id))
        await session.commit()

    logger.info("Task deleted: %s (tenant=%s)", task_id, ctx.tenant_id)
    return {"status": "deleted"}


@router.post("/{task_id}/run")
async def trigger_task(task_id: str, ctx: TenantContext = Depends(get_current_tenant)):
    """Trigger a one-off immediate execution of a task."""
    # Verify task belongs to this tenant
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id, ScheduledTask.tenant_id == ctx.tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Task not found")

    try:
        await run_task_now(task_id)
        return {"status": "triggered", "task_id": task_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-agents")
async def reset_stuck_agents(ctx: TenantContext = Depends(get_current_tenant)):
    """Reset all agents stuck in 'thinking' status to 'idle'."""
    from app.core.agent import agent_manager
    reset_count = 0
    tenant_agents = agent_manager.get_tenant_agents(ctx.tenant_id)
    for agent_id, agent in tenant_agents.items():
        if agent.status == "thinking":
            agent.status = "idle"
            agent.current_task = ""
            reset_count += 1
            # Also sync to DB
            try:
                from app.models.database import AgentState
                from sqlalchemy import update as sql_update
                async with async_session() as session:
                    await session.execute(
                        sql_update(AgentState).where(
                            AgentState.agent_id == agent_id,
                            AgentState.tenant_id == ctx.tenant_id,
                        ).values(
                            status="idle", current_task=""
                        )
                    )
                    await session.commit()
            except Exception:
                pass
    return {"status": "ok", "reset_count": reset_count}
