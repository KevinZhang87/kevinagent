"""Lightweight async scheduler engine — no external deps required."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from app.models.database import async_session, ScheduledTask, TaskExecution

logger = logging.getLogger("kevin_agent.scheduler")

# ── In-memory registry of running tasks ────────────────────────────
_running: dict[str, asyncio.Task] = {}  # task_id -> asyncio.Task


def _parse_interval(interval_str: str) -> timedelta:
    """Parse interval string like '30m', '2h', '1d', '30s' into timedelta."""
    s = interval_str.strip().lower()
    if s.endswith("s"):
        return timedelta(seconds=int(s[:-1]))
    if s.endswith("m"):
        return timedelta(minutes=int(s[:-1]))
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    raise ValueError(f"Invalid interval: {interval_str}. Use e.g. 30s, 10m, 2h, 1d")


async def _execute_task(task_record: ScheduledTask):
    """Run a single scheduled task execution."""
    exec_id = uuid.uuid4().hex[:12]
    started = datetime.utcnow()
    logger.info("Executing scheduled task: %s (exec=%s)", task_record.task_id, exec_id)

    try:
        from app.core.agent import agent_manager

        agent_id = task_record.agent_id or "main"
        agent = agent_manager.get_agent(agent_id)
        if not agent:
            # Agent not in memory — auto-create from DB config or defaults
            logger.info("Agent '%s' not in memory, auto-creating...", agent_id)
            from app.models.database import AgentState
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
                )
            else:
                # Fallback: create with defaults
                import app.config as cfg
                agent = await agent_manager.create_agent(
                    agent_id=agent_id,
                    provider=cfg.default_provider,
                    model=cfg.default_model,
                )
            logger.info("Agent '%s' auto-created (provider=%s, model=%s)",
                        agent_id, agent.provider_name, agent.model)

        # Use a dedicated session for task execution to avoid polluting user chat
        task_session_id = f"task_{task_record.task_id}_{exec_id}"

        # Run agent.chat with the task-specific session
        full_response = ""
        async for chunk in agent.chat(task_record.message, session_id=task_session_id):
            if chunk.type == "text":
                full_response += chunk.content

        elapsed = (datetime.utcnow() - started).total_seconds()
        # Save success execution
        async with async_session() as session:
            execution = TaskExecution(
                execution_id=exec_id,
                task_id=task_record.task_id,
                status="success",
                result=full_response[:5000],
                started_at=started,
                finished_at=datetime.utcnow(),
                duration_ms=int(elapsed * 1000),
            )
            session.add(execution)
            # Update task counters & next_run
            from sqlalchemy import select
            result = await session.execute(
                select(ScheduledTask).where(ScheduledTask.task_id == task_record.task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                task.last_run = datetime.utcnow()
                task.run_count = (task.run_count or 0) + 1
                try:
                    td = _parse_interval(task.interval)
                    task.next_run = datetime.utcnow() + td
                except Exception:
                    task.next_run = None
                session.add(task)
            await session.commit()

        logger.info("Task %s completed in %.1fs", task_record.task_id, elapsed)

    except asyncio.CancelledError:
        # Task was stopped/paused while running — reset agent status to idle
        logger.info("Task %s cancelled during execution, resetting agent status", task_record.task_id)
        try:
            from app.core.agent import agent_manager
            agent_id = task_record.agent_id or "main"
            agent = agent_manager.get_agent(agent_id)
            if agent:
                agent.status = "idle"
                agent.current_task = ""
            # Also sync to DB so frontend shows correct status
            from app.models.database import AgentState
            from sqlalchemy import update as sql_update
            async with async_session() as session:
                await session.execute(
                    sql_update(AgentState).where(AgentState.agent_id == agent_id).values(
                        status="idle", current_task=""
                    )
                )
                await session.commit()
        except Exception as cleanup_err:
            logger.warning("Failed to reset agent status after cancellation: %s", cleanup_err)
        raise  # Re-raise so _task_loop can catch it and break

    except Exception as e:
        elapsed = (datetime.utcnow() - started).total_seconds()
        logger.error("Task %s failed: %s", task_record.task_id, e)
        try:
            async with async_session() as session:
                execution = TaskExecution(
                    execution_id=exec_id,
                    task_id=task_record.task_id,
                    status="failed",
                    result=str(e)[:2000],
                    started_at=started,
                    finished_at=datetime.utcnow(),
                    duration_ms=int(elapsed * 1000),
                )
                session.add(execution)
                # Update fail counter
                from sqlalchemy import select as sel
                task_result = await session.execute(
                    sel(ScheduledTask).where(ScheduledTask.task_id == task_record.task_id)
                )
                task = task_result.scalar_one_or_none()
                if task:
                    task.fail_count = (task.fail_count or 0) + 1
                    task.last_run = datetime.utcnow()
                    try:
                        td = _parse_interval(task.interval)
                        task.next_run = datetime.utcnow() + td
                    except Exception:
                        task.next_run = None
                    session.add(task)
                await session.commit()
        except Exception as db_err:
            logger.error("Failed to record task failure: %s", db_err)


async def _task_loop(task_id: str, interval: timedelta):
    """Background loop that runs a task on interval."""
    while True:
        try:
            await asyncio.sleep(interval.total_seconds())
            # Fetch fresh task record to check if still active
            async with async_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(ScheduledTask).where(ScheduledTask.task_id == task_id)
                )
                task_record = result.scalar_one_or_none()
                if not task_record or not task_record.is_active:
                    logger.info("Task %s deactivated, stopping loop", task_id)
                    break
            await _execute_task(task_record)
        except asyncio.CancelledError:
            logger.info("Task %s cancelled", task_id)
            break
        except Exception as e:
            logger.error("Task loop %s error: %s", task_id, e)
            # Wait a bit before retrying to avoid tight error loop
            await asyncio.sleep(min(interval.total_seconds(), 60))

    _running.pop(task_id, None)


# ── Public API ─────────────────────────────────────────────────────

async def start_task(task_id: str):
    """Start a scheduled task's background loop."""
    if task_id in _running:
        return  # already running

    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task or not task.is_active:
            return

        try:
            interval = _parse_interval(task.interval)
        except ValueError as e:
            logger.error("Invalid interval for task %s: %s", task_id, e)
            return

    t = asyncio.create_task(_task_loop(task_id, interval))
    _running[task_id] = t
    logger.info("Started scheduled task: %s (interval=%s)", task_id, task.interval)


def stop_task(task_id: str):
    """Stop a running task loop and reset associated agent status."""
    t = _running.pop(task_id, None)
    if t and not t.done():
        t.cancel()

    # Reset agent status for task_executor agents
    # Task executors use agent_id like "task_{task_id}" or the configured agent_id
    try:
        from app.core.agent import agent_manager
        # Check all agents and reset any that are stuck in "thinking" from this task
        for agent_id, agent in agent_manager._agents.items():
            if agent.status == "thinking" and (
                agent_id.startswith("task_") or
                f"task_{task_id}" in agent.current_task
            ):
                agent.status = "idle"
                agent.current_task = ""
                logger.info("Reset agent '%s' status to idle (task %s stopped)", agent_id, task_id)
    except Exception as e:
        logger.warning("Failed to reset agent status on task stop: %s", e)


async def start_all_active_tasks():
    """Start all active tasks (called on server startup)."""
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.is_active == True)  # noqa: E712
        )
        tasks = result.scalars().all()
        for task in tasks:
            await start_task(task.task_id)

    logger.info("Scheduler started %d active tasks", len(_running))


def stop_all_tasks():
    """Stop all running tasks (called on server shutdown)."""
    for task_id in list(_running.keys()):
        stop_task(task_id)
    logger.info("All scheduled tasks stopped")


def get_running_task_ids() -> list[str]:
    """Return list of currently running task IDs."""
    return list(_running.keys())


async def run_task_now(task_id: str):
    """Trigger a one-off immediate execution of a task."""
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id)
        )
        task_record = result.scalar_one_or_none()
        if not task_record:
            raise ValueError(f"Task '{task_id}' not found")
    await _execute_task(task_record)
