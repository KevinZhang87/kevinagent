"""Sandbox status API endpoints."""

from fastapi import APIRouter
from app.sandbox.manager import get_sandbox_manager
from app.sandbox.cleaner import get_workspace_cleaner

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.get("/status")
async def sandbox_status():
    """Get current sandbox status and configuration."""
    sandbox = get_sandbox_manager()
    config = sandbox.config

    return {
        "enabled": sandbox.is_enabled,
        "backend": sandbox.backend_name,
        "config": {
            "workspace": config.workspace,
            "docker_image": config.docker_image,
            "memory_limit": config.memory_limit,
            "cpu_limit": config.cpu_limit,
            "timeout": config.timeout,
            "network_disabled": config.network_disabled,
            "max_file_size": config.max_file_size,
        },
    }


@router.post("/test")
async def sandbox_test():
    """Run a simple test command in the sandbox to verify it works."""
    sandbox = get_sandbox_manager()

    if not sandbox.is_enabled:
        return {"success": False, "error": "Sandbox is not enabled"}

    # Test shell execution
    shell_result = await sandbox.execute_command("echo 'Sandbox test: Hello from sandbox!'")

    # Test Python execution
    python_result = await sandbox.execute_python("print('Python sandbox test: Hello from sandbox!')")

    return {
        "backend": sandbox.backend_name,
        "shell_test": {
            "success": shell_result.success,
            "output": shell_result.output,
            "error": shell_result.error,
        },
        "python_test": {
            "success": python_result.success,
            "output": python_result.output,
            "error": python_result.error,
        },
    }


@router.get("/workspaces")
async def workspace_stats():
    """Get disk usage stats for all agent workspaces."""
    cleaner = get_workspace_cleaner()
    return cleaner.get_workspace_stats()


@router.post("/workspaces/cleanup")
async def workspace_cleanup():
    """Manually trigger workspace cleanup (TTL + size-based)."""
    cleaner = get_workspace_cleaner()
    stats = cleaner.run_once()
    return stats
