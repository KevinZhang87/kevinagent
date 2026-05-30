"""Base class for sandbox implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SandboxResult:
    """Result from sandbox execution."""
    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    execution_time: float = 0.0


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    enabled: bool = True
    backend: str = "auto"  # "docker", "local", "auto"
    workspace: str = "./sandbox_workspace"
    docker_image: str = "python:3.11-slim"
    memory_limit: str = "512m"
    cpu_limit: float = 1.0  # CPU cores
    timeout: int = 60
    network_disabled: bool = False
    max_file_size: int = 100_000  # bytes
    readonly_paths: list[str] = None
    blocked_paths: list[str] = None
    blocked_commands: list[str] = None

    def __post_init__(self):
        if self.readonly_paths is None:
            self.readonly_paths = ["/etc", "/sys", "/proc", "C:\\Windows"]
        if self.blocked_paths is None:
            self.blocked_paths = ["/etc/shadow", "/etc/passwd", "C:\\Windows\\System32"]
        if self.blocked_commands is None:
            self.blocked_commands = [
                "rm -rf /", "rm -rf /*", "mkfs", "dd if=",
                "format", "del /s /q C:\\", ":(){ :|:& };:",
                "shutdown", "reboot", "init 0", "init 6",
            ]


class BaseSandbox(ABC):
    """Abstract base class for sandbox implementations."""

    def __init__(self, config: SandboxConfig):
        self.config = config

    @abstractmethod
    async def execute_command(self, command: str, timeout: int = 30) -> SandboxResult:
        """Execute a shell command in the sandbox."""
        pass

    @abstractmethod
    async def execute_python(self, code: str, timeout: int = 30) -> SandboxResult:
        """Execute Python code in the sandbox."""
        pass

    @abstractmethod
    async def read_file(self, path: str) -> SandboxResult:
        """Read a file from the sandbox workspace."""
        pass

    @abstractmethod
    async def write_file(self, path: str, content: str) -> SandboxResult:
        """Write a file to the sandbox workspace."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the sandbox backend is available."""
        pass

    @abstractmethod
    async def cleanup(self):
        """Clean up sandbox resources."""
        pass

    def validate_command(self, command: str) -> Optional[str]:
        """Validate a shell command against security rules. Returns error message or None."""
        cmd_lower = command.lower().strip()
        for blocked in self.config.blocked_commands:
            if blocked.lower() in cmd_lower:
                return f"Command blocked by security policy: contains '{blocked}'"
        return None

    def validate_path(self, path: str, for_write: bool = False) -> Optional[str]:
        """Validate a file path against security rules. Returns error message or None."""
        import os
        # Normalize path
        norm_path = os.path.normpath(path)

        for blocked in self.config.blocked_paths:
            norm_blocked = os.path.normpath(blocked)
            if norm_path.startswith(norm_blocked):
                return f"Path blocked by security policy: '{path}' is under '{blocked}'"

        if for_write:
            for readonly in self.config.readonly_paths:
                norm_readonly = os.path.normpath(readonly)
                if norm_path.startswith(norm_readonly):
                    return f"Path is read-only by security policy: '{path}' is under '{readonly}'"

        return None
