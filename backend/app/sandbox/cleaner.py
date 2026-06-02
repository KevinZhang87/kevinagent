"""Workspace cleaner — TTL-based automatic cleanup of agent workspace files."""
import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

logger = logging.getLogger("kevin_agent.cleaner")

# Default config
DEFAULT_TTL_HOURS = 24
DEFAULT_SHARED_TTL_HOURS = 48
DEFAULT_MAX_SIZE_MB = 200
DEFAULT_INTERVAL_HOURS = 6


def _dir_size_mb(path: Path) -> float:
    """Calculate total size of a directory in MB."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total / (1024 * 1024)


def _cleanup_dir_by_ttl(dir_path: Path, ttl_seconds: int) -> tuple[int, float]:
    """Delete files older than ttl_seconds in dir_path. Returns (deleted_count, freed_mb)."""
    if not dir_path.exists():
        return 0, 0.0

    now = time.time()
    deleted = 0
    freed = 0.0

    for f in sorted(dir_path.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not f.is_file():
            continue
        age = now - f.stat().st_mtime
        if age > ttl_seconds:
            size = f.stat().st_size
            try:
                f.unlink()
                deleted += 1
                freed += size
                logger.debug("Deleted %s (age=%.1fh)", f.name, age / 3600)
            except OSError as e:
                logger.warning("Failed to delete %s: %s", f, e)

    # Remove empty directories
    for d in sorted(dir_path.rglob("*"), key=lambda p: len(str(p)), reverse=True):
        if d.is_dir():
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    return deleted, freed / (1024 * 1024)


def _cleanup_dir_by_size(dir_path: Path, max_size_mb: int) -> tuple[int, float]:
    """Evict oldest files when dir exceeds max_size_mb. Returns (deleted_count, freed_mb)."""
    if not dir_path.exists():
        return 0, 0.0

    current_size = _dir_size_mb(dir_path)
    if current_size <= max_size_mb:
        return 0, 0.0

    # Sort files by modification time (oldest first)
    files = sorted(
        [f for f in dir_path.rglob("*") if f.is_file()],
        key=lambda f: f.stat().st_mtime,
    )

    deleted = 0
    freed = 0.0
    target = current_size - max_size_mb

    for f in files:
        if freed >= target:
            break
        size = f.stat().st_size
        try:
            f.unlink()
            deleted += 1
            freed += size / (1024 * 1024)
            logger.debug("Evicted %s (%.2fMB)", f.name, size / (1024 * 1024))
        except OSError as e:
            logger.warning("Failed to evict %s: %s", f, e)

    return deleted, freed


class WorkspaceCleaner:
    """Periodic cleaner for agent workspaces and shared_workspace."""

    def __init__(
        self,
        workspaces_root: Path | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        shared_ttl_hours: int = DEFAULT_SHARED_TTL_HOURS,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
        interval_hours: int = DEFAULT_INTERVAL_HOURS,
    ):
        self.root = workspaces_root or Path(__file__).parent.parent.parent / "workspaces"
        self.shared_root = self.root.parent / "shared_workspace"
        self.ttl_seconds = ttl_hours * 3600
        self.shared_ttl_seconds = shared_ttl_hours * 3600
        self.max_size_mb = max_size_mb
        self.interval_seconds = interval_hours * 3600
        self._task: asyncio.Task | None = None

    def run_once(self, tenant_id: str = None) -> dict:
        """Run cleanup once and return stats. Optionally scoped to a tenant."""
        stats = {"agent_workspaces": {}, "shared_workspace": {}, "total_deleted": 0, "total_freed_mb": 0.0}

        # Determine root to scan
        if tenant_id:
            scan_root = self.root / tenant_id
        else:
            scan_root = self.root

        # Clean each agent workspace
        if scan_root.exists():
            for agent_dir in scan_root.iterdir():
                if not agent_dir.is_dir():
                    continue
                # Skip shared_workspace directory
                if agent_dir.name == "shared_workspace":
                    continue
                sandbox_dir = agent_dir / "sandbox"
                d1, f1 = _cleanup_dir_by_ttl(sandbox_dir, self.ttl_seconds)
                d2, f2 = _cleanup_dir_by_size(sandbox_dir, self.max_size_mb)
                deleted = d1 + d2
                freed = f1 + f2
                if deleted > 0:
                    stats["agent_workspaces"][agent_dir.name] = {"deleted": deleted, "freed_mb": round(freed, 2)}
                    stats["total_deleted"] += deleted
                    stats["total_freed_mb"] += freed

        # Clean shared workspace
        if tenant_id:
            shared_root = self.root / tenant_id / "shared_workspace"
        else:
            shared_root = self.shared_root
        d, f = _cleanup_dir_by_ttl(shared_root, self.shared_ttl_seconds)
        if d > 0:
            stats["shared_workspace"] = {"deleted": d, "freed_mb": round(f, 2)}
            stats["total_deleted"] += d
            stats["total_freed_mb"] += f

        if stats["total_deleted"] > 0:
            logger.info("Workspace cleanup: deleted %d files, freed %.2fMB", stats["total_deleted"], stats["total_freed_mb"])

        return stats

    async def _loop(self):
        """Background loop that runs cleanup periodically."""
        while True:
            try:
                await asyncio.sleep(self.interval_seconds)
                self.run_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Workspace cleaner error: %s", e)
                await asyncio.sleep(60)

    def start(self):
        """Start the background cleanup loop."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Workspace cleaner started (ttl=%dh, shared_ttl=%dh, max_size=%dMB, interval=%dh)",
                     self.ttl_seconds // 3600, self.shared_ttl_seconds // 3600, self.max_size_mb, self.interval_seconds // 3600)

    def stop(self):
        """Stop the background cleanup loop."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Workspace cleaner stopped")

    def get_workspace_stats(self, tenant_id: str = None) -> dict:
        """Get current workspace disk usage stats. Optionally scoped to a tenant."""
        stats = {"workspaces": {}, "shared_workspace": {"size_mb": 0}}

        if tenant_id:
            scan_root = self.root / tenant_id
        else:
            scan_root = self.root

        if scan_root.exists():
            for agent_dir in scan_root.iterdir():
                if not agent_dir.is_dir():
                    continue
                if agent_dir.name == "shared_workspace":
                    continue
                sandbox_dir = agent_dir / "sandbox"
                stats["workspaces"][agent_dir.name] = {
                    "size_mb": round(_dir_size_mb(sandbox_dir), 2),
                    "file_count": sum(1 for _ in sandbox_dir.rglob("*") if _.is_file()) if sandbox_dir.exists() else 0,
                }

        if tenant_id:
            shared_root = self.root / tenant_id / "shared_workspace"
        else:
            shared_root = self.shared_root
        stats["shared_workspace"] = {
            "size_mb": round(_dir_size_mb(shared_root), 2),
            "file_count": sum(1 for _ in shared_root.rglob("*") if _.is_file()) if shared_root.exists() else 0,
        }

        return stats


# Singleton
_workspace_cleaner: WorkspaceCleaner | None = None


def get_workspace_cleaner() -> WorkspaceCleaner:
    global _workspace_cleaner
    if _workspace_cleaner is None:
        _workspace_cleaner = WorkspaceCleaner()
    return _workspace_cleaner
