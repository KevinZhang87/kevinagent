import logging
from datetime import datetime, timedelta
from fastapi import APIRouter
from sqlalchemy import select, func

from app.models.database import TokenUsage, async_session

logger = logging.getLogger("kevin_agent.stats")

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/tokens/debug")
async def debug_token_usage():
    """Debug endpoint: show recent raw token_usage records."""
    async with async_session() as session:
        result = await session.execute(
            select(TokenUsage).order_by(TokenUsage.created_at.desc()).limit(20)
        )
        records = [
            {
                "id": r.id,
                "session_id": r.session_id,
                "agent_id": r.agent_id,
                "model": r.model,
                "provider": r.provider,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "request_type": r.request_type,
                "created_at": str(r.created_at),
            }
            for r in result.scalars()
        ]
        # Also count total
        count_result = await session.execute(
            select(func.count(TokenUsage.id))
        )
        total_count = count_result.scalar() or 0
        return {"total_records": total_count, "recent_records": records}


@router.get("/tokens")
async def get_token_stats(days: int = 30):
    """Get token usage statistics aggregated by day."""
    since = datetime.utcnow() - timedelta(days=days)

    async with async_session() as session:
        # Daily aggregation (use strftime for SQLite compatibility)
        date_expr = func.strftime("%Y-%m-%d", TokenUsage.created_at).label("date")
        result = await session.execute(
            select(
                date_expr,
                func.sum(TokenUsage.prompt_tokens).label("prompt_tokens"),
                func.sum(TokenUsage.completion_tokens).label("completion_tokens"),
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= since)
            .group_by(date_expr)
            .order_by(date_expr)
        )

        daily = [
            {
                "date": str(row.date),
                "prompt_tokens": row.prompt_tokens or 0,
                "completion_tokens": row.completion_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "request_count": row.request_count or 0,
            }
            for row in result
        ]

        # Totals
        total_result = await session.execute(
            select(
                func.sum(TokenUsage.prompt_tokens).label("prompt_tokens"),
                func.sum(TokenUsage.completion_tokens).label("completion_tokens"),
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= since)
        )
        total_row = total_result.one()

        # By model
        model_result = await session.execute(
            select(
                TokenUsage.model,
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= since)
            .group_by(TokenUsage.model)
            .order_by(func.sum(TokenUsage.total_tokens).desc())
        )

        by_model = [
            {
                "model": row.model,
                "total_tokens": row.total_tokens or 0,
                "request_count": row.request_count or 0,
            }
            for row in model_result
        ]

        return {
            "daily": daily,
            "totals": {
                "prompt_tokens": total_row.prompt_tokens or 0,
                "completion_tokens": total_row.completion_tokens or 0,
                "total_tokens": total_row.total_tokens or 0,
                "request_count": total_row.request_count or 0,
                "days": days,
            },
            "by_model": by_model,
        }


@router.get("/overview")
async def get_overview():
    """Get a quick overview of system statistics."""
    async with async_session() as session:
        # Today's usage
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await session.execute(
            select(
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= today)
        )
        today_row = today_result.one()

        # Total usage
        total_result = await session.execute(
            select(
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
        )
        total_row = total_result.one()

        # Last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_result = await session.execute(
            select(
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= week_ago)
        )
        week_row = week_result.one()

        return {
            "today": {
                "total_tokens": today_row.total_tokens or 0,
                "request_count": today_row.request_count or 0,
            },
            "week": {
                "total_tokens": week_row.total_tokens or 0,
                "request_count": week_row.request_count or 0,
            },
            "all_time": {
                "total_tokens": total_row.total_tokens or 0,
                "request_count": total_row.request_count or 0,
            },
        }


@router.get("/context")
async def get_context_stats():
    """Get context window usage statistics for active agents."""
    from app.core.agent import agent_manager
    from app.config import app_config

    agents_info = []
    for agent_id, agent in agent_manager._agents.items():
        agents_info.append({
            "agent_id": agent_id,
            "model": agent.model,
            "provider": agent.provider_name,
            "context_window": agent.context_window_size,
            "compression_enabled": agent.context_compression_enabled,
            "compression_threshold": agent.context_compression_threshold,
            "status": agent.status,
        })

    return {
        "config": {
            "context_window_size": app_config.agent.context_window_size,
            "compression_enabled": app_config.agent.context_compression_enabled,
            "compression_threshold": app_config.agent.context_compression_threshold,
            "max_messages": app_config.agent.context_max_messages,
        },
        "agents": agents_info,
    }
