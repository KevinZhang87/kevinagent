"""Sandbox status API endpoints."""

from fastapi import APIRouter, Depends
from app.sandbox.manager import get_sandbox_manager
from app.sandbox.cleaner import get_workspace_cleaner
from app.auth.dependencies import get_current_tenant
from app.auth.schema import TenantContext

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.get("/status")
async def sandbox_status(ctx: TenantContext = Depends(get_current_tenant)):
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
async def sandbox_test(ctx: TenantContext = Depends(get_current_tenant)):
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
async def workspace_stats(ctx: TenantContext = Depends(get_current_tenant)):
    """Get disk usage stats for agent workspaces."""
    cleaner = get_workspace_cleaner()
    return cleaner.get_workspace_stats(tenant_id=ctx.tenant_id)


@router.post("/workspaces/cleanup")
async def workspace_cleanup(ctx: TenantContext = Depends(get_current_tenant)):
    """Manually trigger workspace cleanup (TTL + size-based)."""
    cleaner = get_workspace_cleaner()
    stats = cleaner.run_once(tenant_id=ctx.tenant_id)
    return stats
