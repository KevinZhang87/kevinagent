import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.api import chat, agents, skills, models, stats, user_settings, sandbox, tasks, memory
from app.auth.router import router as auth_router
from app.config import app_config

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, app_config.logging.level, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kevin_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting KevinAgent server...")
    await init_db()
    logger.info("Database initialized")

    # Initialize sandbox
    from app.sandbox.manager import get_sandbox_manager
    sandbox = get_sandbox_manager()
    await sandbox.initialize()
    logger.info("Sandbox initialized: backend=%s, enabled=%s", sandbox.backend_name, sandbox.is_enabled)

    # Start scheduler
    from app.scheduler.engine import start_all_active_tasks
    await start_all_active_tasks()
    logger.info("Scheduler initialized")

    # Start workspace cleaner
    from app.sandbox.cleaner import get_workspace_cleaner
    cleaner = get_workspace_cleaner()
    cleaner.start()
    logger.info("Workspace cleaner started")

    # Wire WebSocket broadcast to agent manager
    from app.websocket.handler import ws_manager
    from app.core.agent import agent_manager
    agent_manager.add_ws_callback(ws_manager.send_agent_update)
    logger.info("WebSocket agent broadcast wired")

    # Reset stale agent states from previous crash/restart
    from app.models.database import async_session, AgentState
    from sqlalchemy import update as sql_update
    try:
        async with async_session() as session:
            result = await session.execute(
                sql_update(AgentState).where(
                    AgentState.status.in_(["thinking", "executing", "cancelled"])
                ).values(status="idle", current_task="")
            )
            await session.commit()
            if result.rowcount > 0:
                logger.info("Reset %d stale agent states to idle", result.rowcount)
    except Exception as e:
        logger.warning("Failed to reset stale agent states: %s", e)

    # Load agent_config.json and pre-create configured agents
    agent_config_path = Path(__file__).parent.parent / "agent_config.json"
    if agent_config_path.exists():
        try:
            import app.config as cfg
            with open(agent_config_path, "r", encoding="utf-8") as f:
                agent_cfg = json.load(f)
            for agent_id, agent_data in agent_cfg.get("agents", {}).items():
                # Use configured provider/model, or fall back to default
                provider = agent_data.get("provider") or cfg.default_provider
                model = agent_data.get("model") or cfg.default_model
                await agent_manager.create_agent(
                    agent_id=agent_id,
                    provider=provider,
                    model=model,
                    system_prompt=agent_data.get("system_prompt", ""),
                    tenant_id="default",
                )
                logger.info("Pre-created agent from config: %s (%s/%s)", agent_id, provider, model)
        except Exception as e:
            logger.warning("Failed to load agent_config.json: %s", e)

    logger.info("Server ready on %s:%d", app_config.server.host, app_config.server.port)
    yield
    # Shutdown
    logger.info("Shutting down KevinAgent server")
    from app.scheduler.engine import stop_all_tasks
    stop_all_tasks()
    from app.sandbox.cleaner import get_workspace_cleaner
    get_workspace_cleaner().stop()
    await sandbox.cleanup()


app = FastAPI(
    title="KevinAgent",
    description="Self-evolving AI Agent Framework",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(skills.router)
app.include_router(models.router)
app.include_router(stats.router)
app.include_router(user_settings.router)
app.include_router(sandbox.router)
app.include_router(tasks.router)
app.include_router(memory.router)


@app.get("/")
async def root():
    return {
        "name": "KevinAgent",
        "version": "0.2.0",
        "description": "Self-evolving AI Agent Framework",
    }


@app.get("/health")
async def health():
    from app.sandbox.manager import get_sandbox_manager
    sandbox = get_sandbox_manager()
    return {
        "status": "ok",
        "sandbox": {
            "enabled": sandbox.is_enabled,
            "backend": sandbox.backend_name,
        },
    }
