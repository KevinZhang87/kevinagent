import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.api import chat, agents, skills, models, stats, user_settings, sandbox, tasks, memory
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

    # Wire WebSocket broadcast to agent manager
    from app.websocket.handler import ws_manager
    from app.core.agent import agent_manager
    agent_manager.add_ws_callback(ws_manager.send_agent_update)
    logger.info("WebSocket agent broadcast wired")

    logger.info("Server ready on %s:%d", app_config.server.host, app_config.server.port)
    yield
    # Shutdown
    logger.info("Shutting down KevinAgent server")
    from app.scheduler.engine import stop_all_tasks
    stop_all_tasks()
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
