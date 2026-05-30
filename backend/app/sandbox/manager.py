"""Sandbox Manager - Selects and manages the appropriate sandbox backend.

Strategy:
- If sandbox.enabled is False → no sandbox (direct execution, legacy behavior)
- If backend is "auto" → try Docker first, fall back to local
- If backend is "docker" → use Docker sandbox only
- If backend is "local" → use local sandbox only

Each agent gets an isolated workspace under workspaces/{agent_id}/
"""

import os
import logging
from typing import Optional

from .base import BaseSandbox, SandboxConfig, SandboxResult
from .docker_sandbox import DockerSandbox
from .local_sandbox import LocalSandbox

logger = logging.getLogger(__name__)

# Global sandbox manager instance
_sandbox_manager: Optional["SandboxManager"] = None

# Base directory for agent workspaces
WORKSPACES_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "workspaces")

# Shared workspace for inter-agent collaboration (Blackboard pattern)
SHARED_WORKSPACE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "shared_workspace")


class SandboxManager:
    """Manages sandbox backends and provides a unified interface."""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._sandbox: Optional[BaseSandbox] = None
        self._initialized = False
        self._backend_name: str = "none"
        self._agent_sandboxes: dict[str, BaseSandbox] = {}  # agent_id -> sandbox

    async def initialize(self):
        """Initialize the sandbox backend based on configuration."""
        if self._initialized:
            return

        if not self.config.enabled:
            logger.info("Sandbox is disabled, running without isolation")
            self._backend_name = "disabled"
            self._initialized = True
            return

        backend = self.config.backend.lower()

        if backend == "auto":
            # Try Docker first, then fall back to local
            docker_sandbox = DockerSandbox(self.config)
            if await docker_sandbox.is_available():
                self._sandbox = docker_sandbox
                self._backend_name = "docker"
                logger.info("Sandbox: Using Docker backend")
            else:
                self._sandbox = LocalSandbox(self.config)
                self._backend_name = "local"
                logger.info("Sandbox: Docker not available, using local sandbox with security enforcement")

        elif backend == "docker":
            self._sandbox = DockerSandbox(self.config)
            if await self._sandbox.is_available():
                self._backend_name = "docker"
                logger.info("Sandbox: Using Docker backend")
            else:
                logger.error("Sandbox: Docker backend requested but not available!")
                # Fall back to local rather than no sandbox
                self._sandbox = LocalSandbox(self.config)
                self._backend_name = "local"
                logger.warning("Sandbox: Falling back to local sandbox")

        elif backend == "local":
            self._sandbox = LocalSandbox(self.config)
            self._backend_name = "local"
            logger.info("Sandbox: Using local backend")

        else:
            logger.error(f"Sandbox: Unknown backend '{backend}', disabling sandbox")
            self._backend_name = "disabled"

        self._initialized = True

    def get_agent_sandbox(self, agent_id: str) -> Optional[BaseSandbox]:
        """Get or create a sandbox with isolated workspace for a specific agent."""
        if not self.config.enabled:
            return None

        if agent_id in self._agent_sandboxes:
            return self._agent_sandboxes[agent_id]

        # Create agent-specific workspace: workspaces/{agent_id}/sandbox/
        agent_workspace = os.path.join(WORKSPACES_BASE, agent_id, "sandbox")
        os.makedirs(agent_workspace, exist_ok=True)

        # Create a config with the agent's workspace
        agent_config = SandboxConfig(
            enabled=self.config.enabled,
            backend=self.config.backend,
            workspace=agent_workspace,
            docker_image=self.config.docker_image,
            memory_limit=self.config.memory_limit,
            cpu_limit=self.config.cpu_limit,
            timeout=self.config.timeout,
            network_disabled=self.config.network_disabled,
            max_file_size=self.config.max_file_size,
            readonly_paths=self.config.readonly_paths,
            blocked_paths=self.config.blocked_paths,
            blocked_commands=self.config.blocked_commands,
        )

        # Create sandbox based on backend type
        if self._backend_name == "docker":
            sandbox = DockerSandbox(agent_config)
        else:
            sandbox = LocalSandbox(agent_config)

        self._agent_sandboxes[agent_id] = sandbox
        logger.info("Created sandbox for agent '%s' with workspace: %s", agent_id, agent_workspace)
        return sandbox

    @property
    def backend_name(self) -> str:
        """Get the name of the active backend."""
        return self._backend_name

    @property
    def is_enabled(self) -> bool:
        """Check if sandbox is enabled and active."""
        return self._sandbox is not None

    async def execute_command(self, command: str, timeout: int = 30, agent_id: str = None) -> SandboxResult:
        """Execute a shell command through the sandbox.

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds
            agent_id: Optional agent ID for isolated workspace
        """
        # Use agent-specific sandbox if agent_id provided
        if agent_id:
            agent_sandbox = self.get_agent_sandbox(agent_id)
            if agent_sandbox:
                return await agent_sandbox.execute_command(command, timeout)

        if not self._sandbox:
            # Sandbox disabled - execute directly (legacy behavior)
            return await self._execute_direct(command, timeout)

        return await self._sandbox.execute_command(command, timeout)

    async def execute_python(self, code: str, timeout: int = 30, agent_id: str = None) -> SandboxResult:
        """Execute Python code through the sandbox.

        Args:
            code: Python code to execute
            timeout: Timeout in seconds
            agent_id: Optional agent ID for isolated workspace
        """
        # Use agent-specific sandbox if agent_id provided
        if agent_id:
            agent_sandbox = self.get_agent_sandbox(agent_id)
            if agent_sandbox:
                return await agent_sandbox.execute_python(code, timeout)

        if not self._sandbox:
            # Sandbox disabled - execute directly (legacy behavior)
            return await self._execute_python_direct(code, timeout)

        return await self._sandbox.execute_python(code, timeout)

    async def read_file(self, path: str, agent_id: str = None) -> SandboxResult:
        """Read a file through the sandbox.

        Args:
            path: File path to read
            agent_id: Optional agent ID for isolated workspace
        """
        # Use agent-specific sandbox if agent_id provided
        if agent_id:
            agent_sandbox = self.get_agent_sandbox(agent_id)
            if agent_sandbox:
                return await agent_sandbox.read_file(path)

        if not self._sandbox:
            # Direct file read (legacy)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read(50000)
                return SandboxResult(success=True, output=content)
            except Exception as e:
                return SandboxResult(success=False, output="", error=str(e))

        return await self._sandbox.read_file(path)

    async def write_file(self, path: str, content: str, agent_id: str = None) -> SandboxResult:
        """Write a file through the sandbox.

        Args:
            path: File path to write
            content: Content to write
            agent_id: Optional agent ID for isolated workspace
        """
        # Use agent-specific sandbox if agent_id provided
        if agent_id:
            agent_sandbox = self.get_agent_sandbox(agent_id)
            if agent_sandbox:
                return await agent_sandbox.write_file(path, content)

        if not self._sandbox:
            # Direct file write (legacy)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return SandboxResult(success=True, output=f"Successfully wrote to {path}")
            except Exception as e:
                return SandboxResult(success=False, output="", error=str(e))

        return await self._sandbox.write_file(path, content)

    async def cleanup(self):
        """Clean up sandbox resources."""
        if self._sandbox:
            await self._sandbox.cleanup()

    async def _execute_direct(self, command: str, timeout: int = 30) -> SandboxResult:
        """Direct execution without sandbox (legacy fallback)."""
        import subprocess
        import time

        start_time = time.time()
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, timeout=timeout,
            )
            stdout = LocalSandbox._decode_bytes(result.stdout)
            stderr = LocalSandbox._decode_bytes(result.stderr)
            return SandboxResult(
                success=result.returncode == 0,
                output=stdout[:5000],
                error=stderr[:2000] if result.returncode != 0 else "",
                exit_code=result.returncode,
                execution_time=time.time() - start_time,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False, output="", error=f"Command timed out ({timeout}s)",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                success=False, output="", error=str(e),
                execution_time=time.time() - start_time,
            )

    async def _execute_python_direct(self, code: str, timeout: int = 30) -> SandboxResult:
        """Direct Python execution without sandbox (legacy fallback)."""
        import subprocess
        import sys
        import time

        start_time = time.time()
        try:
            env = {**dict(subprocess.os.environ), "PYTHONIOENCODING": "utf-8"}
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, timeout=timeout, env=env,
            )
            stdout = LocalSandbox._decode_bytes(result.stdout)
            stderr = LocalSandbox._decode_bytes(result.stderr)
            return SandboxResult(
                success=result.returncode == 0,
                output=stdout[:5000],
                error=stderr[:2000] if result.returncode != 0 else "",
                exit_code=result.returncode,
                execution_time=time.time() - start_time,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False, output="", error=f"Python execution timed out ({timeout}s)",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SandboxResult(
                success=False, output="", error=str(e),
                execution_time=time.time() - start_time,
            )


def get_sandbox_manager() -> "SandboxManager":
    """Get the global sandbox manager instance."""
    global _sandbox_manager
    if _sandbox_manager is None:
        from ..config import load_sandbox_config
        config = load_sandbox_config()
        _sandbox_manager = SandboxManager(config)
    return _sandbox_manager


def init_agent_workspace(agent_id: str) -> str:
    """Initialize workspace directory structure for an agent.

    Creates:
        workspaces/{agent_id}/
        workspaces/{agent_id}/sandbox/    # For code execution
        workspaces/{agent_id}/skills/     # For agent-specific skills

    Also ensures shared_workspace/ exists for inter-agent collaboration.

    Returns:
        Path to the agent's workspace root
    """
    workspace_root = os.path.join(WORKSPACES_BASE, agent_id)
    sandbox_dir = os.path.join(workspace_root, "sandbox")
    skills_dir = os.path.join(workspace_root, "skills")

    os.makedirs(sandbox_dir, exist_ok=True)
    os.makedirs(skills_dir, exist_ok=True)

    # Ensure shared workspace exists
    os.makedirs(SHARED_WORKSPACE, exist_ok=True)

    logger.info("Initialized workspace for agent '%s': %s", agent_id, workspace_root)
    return workspace_root


def get_shared_workspace() -> str:
    """Get the shared workspace path, creating it if needed."""
    os.makedirs(SHARED_WORKSPACE, exist_ok=True)
    return SHARED_WORKSPACE


def reset_sandbox_manager():
    """Reset the global sandbox manager (for testing or config reload)."""
    global _sandbox_manager
    if _sandbox_manager:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_sandbox_manager.cleanup())
            else:
                loop.run_until_complete(_sandbox_manager.cleanup())
        except Exception:
            pass
    _sandbox_manager = None
