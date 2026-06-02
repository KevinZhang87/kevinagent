from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, Float, JSON, Boolean, func, Index, text as sa_text
from datetime import datetime
from typing import Optional
import logging

from app.config import app_config

logger = logging.getLogger("kevin_agent.db")

# Create engine with database-specific settings
engine_kwargs: dict = {"echo": app_config.database.echo}

if app_config.database.type == "sqlite":
    # SQLite: enable WAL mode for concurrent reads + writes
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 30,  # seconds to wait for lock before giving up
    }
else:
    engine_kwargs["pool_size"] = app_config.database.pool_size
    engine_kwargs["max_overflow"] = app_config.database.max_overflow

engine = create_async_engine(app_config.database.url, **engine_kwargs)

# Enable SQLite WAL mode on every new connection for concurrent read/write support
if app_config.database.type == "sqlite":
    from sqlalchemy import event
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, default="default")
    title: Mapped[str] = mapped_column(String(256), default="New Chat")
    model: Mapped[str] = mapped_column(String(128), default="gpt-4o")
    provider: Mapped[str] = mapped_column(String(64), default="openai")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32))  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_messages_session_created", "session_id", "created_at"),
    )


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, default="default")
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    memory_type: Mapped[str] = mapped_column(String(32), default="general")  # general, skill, user_preference
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, default="default")
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text)
    instruction: Mapped[str] = mapped_column(Text)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of recent failure contexts
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_skill_tenant_name", "tenant_id", "name", unique=True),
    )


class AgentState(Base):
    __tablename__ = "agent_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, default="default")
    status: Mapped[str] = mapped_column(String(32), default="idle")  # idle, thinking, executing, error
    current_task: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model: Mapped[str] = mapped_column(String(128), default="gpt-4o")
    provider: Mapped[str] = mapped_column(String(64), default="openai")
    ephemeral: Mapped[bool] = mapped_column(Boolean, default=False)  # True for auto-created temporary agents
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    capabilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    tools: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of tool names
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_agent_tenant_agent", "tenant_id", "agent_id", unique=True),
    )


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, default="default")
    agent_id: Mapped[str] = mapped_column(String(64), default="main")
    model: Mapped[str] = mapped_column(String(128), default="")
    provider: Mapped[str] = mapped_column(String(64), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    request_type: Mapped[str] = mapped_column(String(32), default="chat")  # chat, tool_call
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_token_usage_created", "created_at"),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, default="default")
    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True, default="default")
    name: Mapped[str] = mapped_column(String(128), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    interval: Mapped[str] = mapped_column(String(32), default="1h")  # e.g. 30s, 10m, 2h, 1d
    agent_id: Mapped[str] = mapped_column(String(64), default="main")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running, success, failed
    result: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_task_exec_task_id", "task_id"),
    )


async def _migrate_sqlite(conn):
    """Add missing columns to existing SQLite tables (CREATE_ALL doesn't auto-migrate)."""
    if app_config.database.type != "sqlite":
        return

    async def _table_columns(table_name: str) -> set:
        """Get column names for a table."""
        result = await conn.execute(sa_text(f"PRAGMA table_info({table_name})"))
        rows = result.fetchall()
        return {row[1] for row in rows}

    # skills.failure_notes — added for evolve feature context storage
    try:
        columns = await _table_columns("skills")
        if "failure_notes" not in columns:
            await conn.execute(sa_text("ALTER TABLE skills ADD COLUMN failure_notes TEXT"))
            logger.info("Migration: added skills.failure_notes column")
    except Exception as e:
        logger.warning("Migration check for skills.failure_notes failed: %s", e)

    # agent_states.ephemeral — added for auto-cleanup of temporary agents
    try:
        columns = await _table_columns("agent_states")
        if "ephemeral" not in columns:
            await conn.execute(sa_text("ALTER TABLE agent_states ADD COLUMN ephemeral BOOLEAN DEFAULT 0"))
            logger.info("Migration: added agent_states.ephemeral column")
        # agent_states enhanced fields — system_prompt, description, capabilities, tools
        if "system_prompt" not in columns:
            await conn.execute(sa_text("ALTER TABLE agent_states ADD COLUMN system_prompt TEXT"))
            logger.info("Migration: added agent_states.system_prompt column")
        if "description" not in columns:
            await conn.execute(sa_text("ALTER TABLE agent_states ADD COLUMN description VARCHAR(256)"))
            logger.info("Migration: added agent_states.description column")
        if "capabilities" not in columns:
            await conn.execute(sa_text("ALTER TABLE agent_states ADD COLUMN capabilities TEXT"))
            logger.info("Migration: added agent_states.capabilities column")
        if "tools" not in columns:
            await conn.execute(sa_text("ALTER TABLE agent_states ADD COLUMN tools TEXT"))
            logger.info("Migration: added agent_states.tools column")
    except Exception as e:
        logger.warning("Migration check for agent_states enhanced fields failed: %s", e)

    # Multi-tenant: add tenant_id columns to existing tables
    tenant_migrations = [
        ("conversations", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
        ("messages", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
        ("memories", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
        ("skills", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
        ("agent_states", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
        ("token_usage", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
        ("user_settings", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
        ("scheduled_tasks", "tenant_id", "VARCHAR(64) DEFAULT 'default'"),
    ]
    for table, column, col_def in tenant_migrations:
        try:
            columns = await _table_columns(table)
            if column not in columns:
                await conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                logger.info("Migration: added %s.%s column", table, column)
        except Exception as e:
            logger.warning("Migration check for %s.%s failed: %s", table, column, e)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_sqlite(conn)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
