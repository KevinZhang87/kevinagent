"""
Memory backend package.

Provides a pluggable interface for long-term memory storage.
Default: SQLite (keyword search). Optional: mem0 (semantic vector search).

Usage:
    from app.memory import get_memory_backend, BaseMemoryBackend

    backend = get_memory_backend(session_id="abc")
    await backend.save_memory("User prefers dark mode", importance=0.8, memory_type="user_preference")
    results = await backend.get_relevant_memories("dark mode")
"""

import logging
from typing import Optional

from .base import BaseMemoryBackend

logger = logging.getLogger("kevin_agent.memory")


def get_memory_backend(session_id: str, tenant_id: Optional[str] = None) -> BaseMemoryBackend:
    """Factory function: create the appropriate memory backend based on app config.

    Args:
        session_id: The session this backend is bound to.
        tenant_id: Optional tenant scope for multi-tenant filtering.

    Returns:
        An instance of BaseMemoryBackend (SqliteMemoryBackend or Mem0MemoryBackend).
    """
    from app.config import app_config

    backend_type = getattr(app_config, "memory_backend", "sqlite")

    if backend_type == "mem0":
        from .mem0_backend import Mem0MemoryBackend
        mem0_config = getattr(app_config, "memory_config", {})
        logger.info("Using mem0 memory backend (session=%s)", session_id[:8])
        return Mem0MemoryBackend(session_id, tenant_id=tenant_id, config=mem0_config)

    # Default: SQLite
    from .sqlite_backend import SqliteMemoryBackend
    return SqliteMemoryBackend(session_id, tenant_id=tenant_id)


__all__ = ["BaseMemoryBackend", "get_memory_backend"]
