"""Local sandbox implementation with security enforcement.

When Docker is not available, this provides a fallback sandbox that enforces
command blocking, path restrictions, and resource limits.
"""

import os
import subprocess
import sys
import time
import logging
from typing import Optional

from .base import BaseSandbox, SandboxConfig, SandboxResult

logger = logging.getLogger(__name__)


class LocalSandbox(BaseSandbox):
    """Local sandbox with command/path validation and restricted execution."""

    def __init__(self, config: SandboxConfig):
        super().__init__(config)
        self._workspace_path = os.path.abspath(config.workspace)
        os.makedirs(self._workspace_path, exist_ok=True)

    async def is_available(self) -> bool:
        """Local sandbox is always available."""
        return True

    async def execute_command(self, command: str, timeout: int = 30) -> SandboxResult:
        """Execute a shell command with security validation."""
        # Security validation
        validation_error = self.validate_command(command)
        if validation_error:
            return SandboxResult(success=False, output="", error=validation_error)

        start_time = time.time()

        try:
            # Set up restricted environment
            env = self._build_safe_env()

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout,
                env=env,
                cwd=self._workspace_path,
            )

            stdout = self._decode_bytes(result.stdout)
            stderr = self._decode_bytes(result.stderr)

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

    async def execute_python(self, code: str, timeout: int = 30) -> SandboxResult:
        """Execute Python code with security validation."""
        # Check for dangerous imports in the code
        danger_check = self._check_python_danger(code)
        if danger_check:
            return SandboxResult(success=False, output="", error=danger_check)

        start_time = time.time()

        try:
            env = self._build_safe_env()
            env["PYTHONIOENCODING"] = "utf-8"

            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                timeout=timeout,
                env=env,
                cwd=self._workspace_path,
            )

            stdout = self._decode_bytes(result.stdout)
            stderr = self._decode_bytes(result.stderr)

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

    async def read_file(self, path: str) -> SandboxResult:
        """Read a file with path validation."""
        # Security validation
        validation_error = self.validate_path(path, for_write=False)
        if validation_error:
            return SandboxResult(success=False, output="", error=validation_error)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read(self.config.max_file_size)
            return SandboxResult(success=True, output=content)
        except Exception as e:
            return SandboxResult(success=False, output="", error=str(e))

    async def write_file(self, path: str, content: str) -> SandboxResult:
        """Write a file with path validation."""
        # Security validation
        validation_error = self.validate_path(path, for_write=True)
        if validation_error:
            return SandboxResult(success=False, output="", error=validation_error)

        # Size check
        if len(content) > self.config.max_file_size:
            return SandboxResult(
                success=False, output="",
                error=f"Content exceeds max file size ({self.config.max_file_size} bytes)",
            )

        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return SandboxResult(success=True, output=f"Successfully wrote to {path}")
        except Exception as e:
            return SandboxResult(success=False, output="", error=str(e))

    async def cleanup(self):
        """No cleanup needed for local sandbox."""
        pass

    @staticmethod
    def _decode_bytes(data: bytes) -> str:
        """Decode subprocess output bytes with multiple encoding attempts.

        Tries UTF-8 first, then common East Asian encodings (GBK/GB2312/CP936),
        then Western encodings, falling back to UTF-8 with replacement characters.
        """
        if not data:
            return ""
        for enc in ("utf-8", "gbk", "gb2312", "cp936", "cp1252", "latin-1"):
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode("utf-8", errors="replace")

    def _build_safe_env(self) -> dict:
        """Build a safe environment for subprocess execution."""
        # Copy current env but remove sensitive keys
        env = dict(os.environ)

        # Remove sensitive environment variables
        sensitive_keys = [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
            "MOONSHOT_API_KEY", "GLM_API_KEY", "MIMO_API_KEY",
            "DATABASE_URL", "DB_PASSWORD",
        ]
        for key in sensitive_keys:
            env.pop(key, None)
            # Also check for variations
            for k in list(env.keys()):
                if k.upper() == key:
                    del env[k]

        # Force sandbox workspace as working directory hint
        env["SANDBOX_WORKSPACE"] = self._workspace_path

        return env

    def _check_python_danger(self, code: str) -> Optional[str]:
        """Check Python code for obviously dangerous patterns."""
        dangerous_patterns = [
            ("os.system(", "os.system() is not allowed in sandbox"),
            ("subprocess.", "subprocess module is not allowed in sandbox"),
            ("shutil.rmtree(", "shutil.rmtree() is not allowed in sandbox"),
            ("os.remove(", "os.remove() may be restricted"),
            ("__import__", "__import__() is not allowed in sandbox"),
        ]

        code_lower = code.lower()
        for pattern, message in dangerous_patterns:
            if pattern.lower() in code_lower:
                return f"Security: {message}. Use the shell tool instead."

        return None
