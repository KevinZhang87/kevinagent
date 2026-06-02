"""
Base abstract class for long-term memory backends.

Defines the interface that all memory backends (SQLite, mem0, etc.) must implement.
Short-term memory (messages) and conversation management are NOT part of this interface
-- they remain in MemoryManager with direct SQLite access.
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseMemoryBackend(ABC):
    """Abstract interface for long-term memory storage backends.

    All methods return data in a consistent dict format matching the current
    SQLite implementation, so callers (MemoryManager, API layer) are backend-agnostic.

    Args:
        session_id: The session this backend is bound to.
        tenant_id: Optional tenant scope. When set, all operations are filtered
                   by this tenant. Used by the API layer for multi-tenant isolation.
                   MemoryManager (agent-side) leaves this as None.
    """

    def __init__(self, session_id: str, tenant_id: Optional[str] = None):
        self.session_id = session_id
        self.tenant_id = tenant_id

    @abstractmethod
    async def save_memory(self, content: str, importance: float = 0.5, memory_type: str = "general") -> None:
        """Save a new long-term memory."""
        ...

    @abstractmethod
    async def get_relevant_memories(self, query: str = "", limit: int = 5) -> list[dict]:
        """Retrieve memories relevant to a query.

        Returns list of dicts with keys: id, content, importance, type, created_at (ISO string).
        """
        ...

    @abstractmethod
    async def get_all_memories(self, session_id: str = None, memory_type: str = None, limit: int = 100) -> list[dict]:
        """List all memories with optional filtering.

        Returns list of dicts with keys: id, session_id, content, importance, type, created_at (ISO string).
        """
        ...

    @abstractmethod
    async def get_memory_stats(self) -> dict:
        """Get memory statistics.

        Returns dict with keys: total (int), by_type (dict), sessions_with_memories (int).
        """
        ...

    @abstractmethod
    async def delete_memory(self, memory_id) -> bool:
        """Delete a specific memory by ID. Returns True if deleted."""
        ...

    @abstractmethod
    async def update_memory(self, memory_id, content: str = None, importance: float = None, memory_type: str = None) -> bool:
        """Update a specific memory. Returns True if updated."""
        ...

    @abstractmethod
    async def cleanup_memories(self, max_age_days: int = 30, min_importance: float = 0.3, dry_run: bool = False) -> list:
        """Remove old, low-importance memories. Returns list of deleted IDs."""
        ...
