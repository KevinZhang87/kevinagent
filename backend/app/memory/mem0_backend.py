"""
mem0-based long-term memory backend.

Uses the mem0ai SDK for semantic vector search over memories.
Requires: pip install mem0ai
Also needs a running vector store (e.g. Qdrant) and an LLM/embedding provider.

This module uses lazy imports so the rest of the app doesn't break when
mem0ai is not installed.
"""

import logging
from datetime import datetime
from typing import Optional

from .base import BaseMemoryBackend

logger = logging.getLogger("kevin_agent.memory.mem0")


class Mem0MemoryBackend(BaseMemoryBackend):
    """Long-term memory powered by mem0 (vector + semantic search).

    Args:
        session_id: Used as mem0's user_id scope.
        tenant_id: Optional multi-tenant scope (stored in metadata).
        config: mem0 Memory configuration dict. If None, uses defaults
                from app config.
    """

    def __init__(self, session_id: str, tenant_id: Optional[str] = None, config: Optional[dict] = None):
        super().__init__(session_id, tenant_id)
        self._config = config or {}
        self._memory = None  # Lazy init

    def _get_memory(self):
        """Lazy-initialize the mem0 Memory client."""
        if self._memory is not None:
            return self._memory

        try:
            from mem0 import Memory
        except ImportError:
            raise ImportError(
                "mem0ai is not installed. Install it with: pip install mem0ai\n"
                "Also ensure a vector store (e.g. Qdrant) is running."
            )

        mem0_config = self._build_config()
        if mem0_config:
            self._memory = Memory.from_config(mem0_config)
        else:
            self._memory = Memory()

        logger.info("mem0 Memory client initialized (session=%s)", self.session_id[:8])
        return self._memory

    def _build_config(self) -> Optional[dict]:
        """Build mem0 config dict from app config."""
        if not self._config:
            return None

        config = {}

        # Vector store config
        vs = self._config.get("vector_store", {})
        if vs:
            config["vector_store"] = {
                "provider": vs.get("provider", "qdrant"),
                "config": {
                    "host": vs.get("host", "localhost"),
                    "port": vs.get("port", 6333),
                },
            }

        # LLM config (used by mem0 for memory extraction)
        llm = self._config.get("llm", {})
        if llm:
            import os
            api_key = os.getenv("OPENAI_API_KEY", "")
            config["llm"] = {
                "provider": llm.get("provider", "openai"),
                "config": {
                    "model": llm.get("model", "gpt-4o-mini"),
                    "api_key": api_key,
                },
            }

        # Embedder config
        embedder = self._config.get("embedder", {})
        if embedder:
            import os
            api_key = os.getenv("OPENAI_API_KEY", "")
            config["embedder"] = {
                "provider": embedder.get("provider", "openai"),
                "config": {
                    "model": embedder.get("model", "text-embedding-3-small"),
                    "api_key": api_key,
                },
            }

        return config if config else None

    def _scope_kwargs(self) -> dict:
        """Return mem0 scope kwargs (user_id for session-level, optionally agent_id)."""
        return {"user_id": self.session_id}

    def _build_metadata(self, importance: float = 0.5, memory_type: str = "general") -> dict:
        """Build metadata dict for mem0 add() calls."""
        meta = {
            "importance": importance,
            "memory_type": memory_type,
        }
        if self.tenant_id:
            meta["tenant_id"] = self.tenant_id
        return meta

    def _adapt_result(self, item: dict) -> dict:
        """Convert a mem0 result item to our standard dict format."""
        metadata = item.get("metadata", {})
        created_at = item.get("created_at", "")
        # mem0 may return different timestamp formats; normalize to ISO
        if isinstance(created_at, str) and created_at:
            pass  # already a string
        elif hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        else:
            created_at = datetime.utcnow().isoformat()

        return {
            "id": item.get("id", ""),
            "content": item.get("memory", item.get("text", "")),
            "importance": metadata.get("importance", 0.5),
            "type": metadata.get("memory_type", "general"),
            "created_at": created_at,
        }

    async def save_memory(self, content: str, importance: float = 0.5, memory_type: str = "general") -> None:
        m = self._get_memory()
        metadata = self._build_metadata(importance, memory_type)
        result = m.add(content, metadata=metadata, **self._scope_kwargs())
        logger.info("mem0 memory saved: type=%s importance=%.1f len=%d", memory_type, importance, len(content))

    async def get_relevant_memories(self, query: str = "", limit: int = 5) -> list[dict]:
        m = self._get_memory()
        if not query or not query.strip():
            # No query: fall back to get_all and sort by importance
            all_mems = m.get_all(**self._scope_kwargs())
            results = all_mems if isinstance(all_mems, list) else all_mems.get("results", [])
            adapted = [self._adapt_result(r) for r in results]
            adapted.sort(key=lambda x: x["importance"], reverse=True)
            return adapted[:limit]

        results = m.search(query, limit=limit, **self._scope_kwargs())
        items = results if isinstance(results, list) else results.get("results", [])
        # Filter by tenant_id in metadata if set
        if self.tenant_id:
            items = [r for r in items if r.get("metadata", {}).get("tenant_id") == self.tenant_id]
        return [self._adapt_result(r) for r in items]

    async def get_all_memories(self, session_id: str = None, memory_type: str = None, limit: int = 100) -> list[dict]:
        m = self._get_memory()
        scope = {"user_id": session_id} if session_id else self._scope_kwargs()
        results = m.get_all(**scope)
        items = results if isinstance(results, list) else results.get("results", [])

        # Filter by tenant_id in metadata if set
        if self.tenant_id:
            items = [r for r in items if r.get("metadata", {}).get("tenant_id") == self.tenant_id]
        # Filter by memory_type in metadata if set
        if memory_type:
            items = [r for r in items if r.get("metadata", {}).get("memory_type") == memory_type]

        adapted = [self._adapt_result(r) for r in items]
        adapted.sort(key=lambda x: x["importance"], reverse=True)
        return adapted[:limit]

    async def get_memory_stats(self) -> dict:
        m = self._get_memory()
        results = m.get_all(**self._scope_kwargs())
        items = results if isinstance(results, list) else results.get("results", [])

        if self.tenant_id:
            items = [r for r in items if r.get("metadata", {}).get("tenant_id") == self.tenant_id]

        total = len(items)
        by_type: dict = {}
        sessions: set = set()

        for item in items:
            meta = item.get("metadata", {})
            mtype = meta.get("memory_type", "general")
            importance = meta.get("importance", 0.5)
            uid = item.get("user_id", "")
            if uid:
                sessions.add(uid)

            if mtype not in by_type:
                by_type[mtype] = {"count": 0, "total_importance": 0.0}
            by_type[mtype]["count"] += 1
            by_type[mtype]["total_importance"] += importance

        # Compute averages
        for v in by_type.values():
            v["avg_importance"] = round(v.pop("total_importance") / v["count"], 2) if v["count"] else 0

        return {
            "total": total,
            "by_type": by_type,
            "sessions_with_memories": len(sessions),
        }

    async def delete_memory(self, memory_id) -> bool:
        m = self._get_memory()
        try:
            m.delete(str(memory_id))
            return True
        except Exception as e:
            logger.warning("mem0 delete failed for %s: %s", memory_id, e)
            return False

    async def update_memory(self, memory_id, content: str = None, importance: float = None, memory_type: str = None) -> bool:
        m = self._get_memory()
        try:
            data = {}
            metadata = {}
            if content is not None:
                data["text"] = content
            if importance is not None:
                metadata["importance"] = importance
            if memory_type is not None:
                metadata["memory_type"] = memory_type
            if metadata:
                data["metadata"] = metadata
            m.update(str(memory_id), **data)
            return True
        except Exception as e:
            logger.warning("mem0 update failed for %s: %s", memory_id, e)
            return False

    async def cleanup_memories(self, max_age_days: int = 30, min_importance: float = 0.3, dry_run: bool = False) -> list:
        m = self._get_memory()
        results = m.get_all(**self._scope_kwargs())
        items = results if isinstance(results, list) else results.get("results", [])

        if self.tenant_id:
            items = [r for r in items if r.get("metadata", {}).get("tenant_id") == self.tenant_id]

        cutoff = datetime.utcnow().timestamp() - (max_age_days * 86400)
        to_delete = []
        for item in items:
            meta = item.get("metadata", {})
            importance = meta.get("importance", 0.5)
            created_at = item.get("created_at", "")
            # Parse timestamp
            try:
                if isinstance(created_at, str) and created_at:
                    ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
                elif hasattr(created_at, "timestamp"):
                    ts = created_at.timestamp()
                else:
                    continue
            except (ValueError, AttributeError):
                continue

            if importance < min_importance and ts < cutoff:
                to_delete.append(item.get("id"))

        if to_delete and not dry_run:
            for mid in to_delete:
                try:
                    m.delete(str(mid))
                except Exception as e:
                    logger.warning("mem0 cleanup delete failed for %s: %s", mid, e)
            logger.info("mem0 cleaned up %d old memories", len(to_delete))

        return to_delete
