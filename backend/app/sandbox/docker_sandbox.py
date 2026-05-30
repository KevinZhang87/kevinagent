"""Docker-based sandbox implementation.

Runs shell commands and Python code inside ephemeral Docker containers
with resource limits, network isolation, and automatic cleanup.
"""

import asyncio
import os
import time
import logging

from .base import BaseSandbox, SandboxConfig, SandboxResult

logger = logging.getLogger(__name__)


class DockerSandbox(BaseSandbox):
    """Sandbox that uses Docker containers for isolated execution."""

    def __init__(self, config: SandboxConfig):
        super().__init__(config)
        self._client = None
        self._workspace_path = os.path.abspath(config.workspace)
        # Ensure workspace directory exists
        os.makedirs(self._workspace_path, exist_ok=True)

    async def _get_client(self):
        """Get or create Docker client."""
        if self._client is None:
            try:
                import aiodocker
                self._client = aiodocker.Docker()
            except ImportError:
                logger.warning("aiodocker not installed, Docker sandbox unavailable")
                return None
        return self._client

    async def is_available(self) -> bool:
        """Check if Docker is available and running."""
        try:
            client = await self._get_client()
            if client is None:
                return False
            await client.system.ping()
            # Also check if the configured image is available
            try:
                await client.images.inspect(self.config.docker_image)
            except Exception:
                logger.info(f"Docker image '{self.config.docker_image}' not found locally, pulling...")
                try:
                    await client.images.pull(self.config.docker_image)
                    logger.info(f"Successfully pulled Docker image '{self.config.docker_image}'")
                except Exception as pull_err:
                    logger.warning(f"Failed to pull Docker image: {pull_err}")
                    return False
            return True
        except Exception as e:
            logger.warning(f"Docker not available: {e}")
            return False

    async def execute_command(self, command: str, timeout: int = 30) -> SandboxResult:
        """Execute a shell command inside a Docker container."""
        # Security validation
        validation_error = self.validate_command(command)
        if validation_error:
            return SandboxResult(success=False, output="", error=validation_error)

        client = await self._get_client()
        if client is None:
            return SandboxResult(success=False, output="", error="Docker client not available")

        start_time = time.time()
        container = None

        try:
            # Create container config
            container_config = self._build_container_config(
                command=command,
                timeout=timeout,
            )

            # Create and start container
            container = await client.containers.create_or_replace(
                config=container_config,
                name=f"kevin-agent-sandbox-{int(time.time() * 1000)}",
            )
            await container.start()

            # Wait for completion with timeout
            try:
                await asyncio.wait_for(
                    self._wait_for_container(container),
                    timeout=timeout + 10,  # Extra buffer
                )
            except asyncio.TimeoutError:
                await container.kill()
                return SandboxResult(
                    success=False, output="", error=f"Execution timed out ({timeout}s)",
                    execution_time=time.time() - start_time,
                )

            # Get exit code and logs
            info = await container.show()
            exit_code = info["State"].get("ExitCode", -1)

            # Get stdout/stderr
            logs = await container.log(stdout=True, stderr=True)
            output = "\n".join(logs) if isinstance(logs, list) else str(logs)

            # Truncate output
            max_out = self.config.max_file_size
            if len(output) > max_out:
                output = output[:max_out] + f"\n... [truncated, {len(output)} bytes total]"

            return SandboxResult(
                success=exit_code == 0,
                output=output[:5000],
                error="" if exit_code == 0 else output[:2000],
                exit_code=exit_code,
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            logger.error(f"Docker sandbox execution error: {e}")
            return SandboxResult(
                success=False, output="", error=f"Sandbox error: {str(e)}",
                execution_time=time.time() - start_time,
            )
        finally:
            if container:
                try:
                    await container.delete(force=True)
                except Exception:
                    pass

    async def execute_python(self, code: str, timeout: int = 30) -> SandboxResult:
        """Execute Python code inside a Docker container."""
        # Wrap code in a Python execution command
        # Use a temp file approach to avoid shell escaping issues
        escaped_code = code.replace("'", "'\\''")
        command = f"python3 -c '{escaped_code}'"
        return await self.execute_command(command, timeout=timeout)

    async def read_file(self, path: str) -> SandboxResult:
        """Read a file from the sandbox workspace."""
        # Security validation
        validation_error = self.validate_path(path, for_write=False)
        if validation_error:
            return SandboxResult(success=False, output="", error=validation_error)

        # For Docker sandbox, resolve path relative to workspace
        safe_path = self._resolve_safe_path(path)

        # Use cat command to read file from container
        result = await self.execute_command(f"cat '{safe_path}'", timeout=10)

        if result.success:
            # Also handle the case where the file is in the workspace mount
            local_path = os.path.join(self._workspace_path, os.path.relpath(path, "/"))
            if os.path.exists(local_path):
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        content = f.read(self.config.max_file_size)
                    return SandboxResult(success=True, output=content)
                except Exception as e:
                    return SandboxResult(success=False, output="", error=str(e))

        return result

    async def write_file(self, path: str, content: str) -> SandboxResult:
        """Write a file to the sandbox workspace."""
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

        # For Docker sandbox, write to the local workspace which is mounted
        try:
            # Determine local path within workspace
            rel_path = path.lstrip("/").lstrip("\\")
            if not rel_path:
                rel_path = os.path.basename(path)
            local_path = os.path.join(self._workspace_path, rel_path)

            # Create parent directories
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            with open(local_path, "w", encoding="utf-8") as f:
                f.write(content)

            return SandboxResult(success=True, output=f"Successfully wrote to {path}")
        except Exception as e:
            return SandboxResult(success=False, output="", error=str(e))

    async def cleanup(self):
        """Clean up Docker resources."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    def _build_container_config(self, command: str, timeout: int = 30) -> dict:
        """Build Docker container configuration."""
        config = {
            "Image": self.config.docker_image,
            "Cmd": ["/bin/sh", "-c", command],
            "WorkingDir": "/workspace",
            "Tty": False,
            "OpenStdin": False,
            "HostConfig": {
                "Binds": [
                    f"{self._workspace_path}:/workspace",
                ],
                "Memory": self._parse_memory(self.config.memory_limit),
                "NanoCpus": int(self.config.cpu_limit * 1e9),
                "AutoRemove": False,
                "PidsLimit": 100,
            },
            "Labels": {
                "kevinagent.sandbox": "true",
                "kevinagent.managed": "true",
            },
        }

        # Network isolation
        if self.config.network_disabled:
            config["HostConfig"]["NetworkMode"] = "none"

        # Security options
        config["HostConfig"].update({
            "ReadonlyRootfs": False,
            "SecurityOpt": ["no-new-privileges:true"],
            "CapDrop": ["ALL"],
        })

        return config

    def _resolve_safe_path(self, path: str) -> str:
        """Resolve a path to be safe within the container's workspace."""
        # Ensure path is within /workspace
        norm = os.path.normpath(path)
        if norm.startswith("/workspace"):
            return norm
        # Put it under /workspace
        return f"/workspace/{os.path.basename(norm)}"

    @staticmethod
    def _parse_memory(mem_str: str) -> int:
        """Parse memory string like '512m' to bytes."""
        mem_str = mem_str.strip().lower()
        if mem_str.endswith("g"):
            return int(float(mem_str[:-1]) * 1024 * 1024 * 1024)
        elif mem_str.endswith("m"):
            return int(float(mem_str[:-1]) * 1024 * 1024)
        elif mem_str.endswith("k"):
            return int(float(mem_str[:-1]) * 1024)
        return int(mem_str)

    async def _wait_for_container(self, container) -> dict:
        """Wait for a container to finish."""
        while True:
            info = await container.show()
            if info["State"].get("Status") != "running":
                return info
            await asyncio.sleep(0.1)
