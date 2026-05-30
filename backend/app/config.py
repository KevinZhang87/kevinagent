"""
KevinAgent Configuration System

Configuration priority (highest to lowest):
1. Environment variables
2. .env file
3. YAML config files in config/ directory
4. Default values in code
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Config directory path
CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_yaml(filename: str) -> dict:
    """Load a YAML config file."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with fallback."""
    return os.getenv(key, default)


# ============================================
# Database URL Builder
# ============================================

def build_database_url(db_config: dict) -> str:
    """Build database connection URL from config."""
    # Check for explicit URL in env
    env_url = get_env("DATABASE_URL")
    if env_url:
        return env_url

    db_type = db_config.get("type", "sqlite")

    if db_type == "sqlite":
        path = db_config.get("sqlite_path", "./kevin.db")
        return f"sqlite+aiosqlite:///{path}"

    elif db_type == "mysql":
        host = get_env("DB_HOST", db_config.get("host", "localhost"))
        port = int(get_env("DB_PORT", str(db_config.get("port", 3306))))
        name = get_env("DB_NAME", db_config.get("name", "kevin_agent"))
        user = get_env("DB_USER", db_config.get("user", "root"))
        password = get_env("DB_PASSWORD", db_config.get("password", ""))
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{name}"

    elif db_type == "postgresql":
        host = get_env("DB_HOST", db_config.get("host", "localhost"))
        port = int(get_env("DB_PORT", str(db_config.get("port", 5432))))
        name = get_env("DB_NAME", db_config.get("name", "kevin_agent"))
        user = get_env("DB_USER", db_config.get("user", "postgres"))
        password = get_env("DB_PASSWORD", db_config.get("password", ""))
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    else:
        raise ValueError(f"Unsupported database type: {db_type}. Use: sqlite, mysql, postgresql")


# ============================================
# App Configuration
# ============================================

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])


@dataclass
class DatabaseConfig:
    url: str = "sqlite+aiosqlite:///./kevin.db"
    type: str = "sqlite"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@dataclass
class AgentConfig:
    max_iterations: int = 30
    max_memory_items: int = 100
    system_prompt: str = ""
    context_window_size: int = 128000
    context_compression_enabled: bool = True
    context_compression_threshold: float = 0.8
    context_max_messages: int = 50


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    active_providers: list[str] = field(default_factory=lambda: ["openai", "deepseek", "moonshot", "glm", "mimo", "anthropic", "ollama"])


def load_app_config() -> AppConfig:
    """Load app configuration from YAML + env vars."""
    data = load_yaml("app.yaml")

    server_data = data.get("server", {})
    db_data = data.get("database", {})
    agent_data = data.get("agent", {})
    log_data = data.get("logging", {})
    active_providers = data.get("active_providers", ["openai", "deepseek", "moonshot", "glm", "mimo", "anthropic", "ollama"])

    db_url = build_database_url(db_data)

    return AppConfig(
        server=ServerConfig(
            host=get_env("HOST", server_data.get("host", "0.0.0.0")),
            port=int(get_env("PORT", str(server_data.get("port", 8000)))),
            debug=server_data.get("debug", True),
            cors_origins=server_data.get("cors_origins", ["http://localhost:3000"]),
        ),
        database=DatabaseConfig(
            url=db_url,
            type=db_data.get("type", "sqlite"),
            echo=db_data.get("echo", False),
            pool_size=int(get_env("DB_POOL_SIZE", str(db_data.get("pool_size", 5)))),
            max_overflow=int(get_env("DB_MAX_OVERFLOW", str(db_data.get("max_overflow", 10)))),
        ),
        agent=AgentConfig(
            max_iterations=int(get_env("MAX_ITERATIONS", str(agent_data.get("max_iterations", 30)))),
            max_memory_items=int(get_env("MAX_MEMORY_ITEMS", str(agent_data.get("max_memory_items", 100)))),
            system_prompt=agent_data.get("system_prompt", ""),
            context_window_size=int(get_env("CONTEXT_WINDOW_SIZE", str(agent_data.get("context_window_size", 128000)))),
            context_compression_enabled=agent_data.get("context_compression_enabled", True),
            context_compression_threshold=float(agent_data.get("context_compression_threshold", 0.8)),
            context_max_messages=int(get_env("CONTEXT_MAX_MESSAGES", str(agent_data.get("context_max_messages", 50)))),
        ),
        logging=LoggingConfig(
            level=get_env("LOG_LEVEL", log_data.get("level", "INFO")),
            format=log_data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        ),
        active_providers=active_providers,
    )


# ============================================
# Provider Configuration
# ============================================

@dataclass
class ModelInfo:
    id: str
    name: str
    max_tokens: int = 4096


@dataclass
class ProviderConfig:
    name: str
    id: str
    base_url: str = ""
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)
    is_configured: bool = False


def load_providers_config() -> dict[str, ProviderConfig]:
    """Load provider configurations from YAML + env vars."""
    data = load_yaml("providers.yaml")
    providers_data = data.get("providers", {})

    providers = {}
    for pid, pdata in providers_data.items():
        api_key_env = pdata.get("api_key_env")
        api_key = get_env(api_key_env, "") if api_key_env else ""

        models = []
        for m in pdata.get("models", []):
            models.append(ModelInfo(
                id=m["id"],
                name=m.get("name", m["id"]),
                max_tokens=m.get("max_tokens", 4096),
            ))

        providers[pid] = ProviderConfig(
            name=pdata["name"],
            id=pid,
            base_url=pdata.get("base_url", ""),
            api_key=api_key,
            models=models,
            is_configured=bool(api_key) if api_key_env else True,
        )

    return providers


def get_default_provider() -> tuple[str, str]:
    """Get default provider and model IDs."""
    data = load_yaml("providers.yaml")
    defaults = data.get("defaults", {})
    return (
        get_env("DEFAULT_PROVIDER", defaults.get("provider", "openai")),
        get_env("DEFAULT_MODEL", defaults.get("model", "gpt-4o")),
    )


# ============================================
# Tool Configuration
# ============================================

@dataclass
class ToolConfig:
    enabled: bool = True
    timeout: int = 30
    max_output: int = 5000
    extra: dict = field(default_factory=dict)


@dataclass
class SkillConfig:
    auto_create: bool = True
    min_tool_calls: int = 2
    min_messages: int = 4
    auto_evolve: bool = True
    evolve_threshold: int = 3


@dataclass
class ToolsConfig:
    tools: dict[str, ToolConfig] = field(default_factory=dict)
    skills: SkillConfig = field(default_factory=SkillConfig)


def load_tools_config() -> ToolsConfig:
    """Load tool configurations from YAML."""
    data = load_yaml("tools.yaml")

    tools = {}
    for tname, tdata in data.get("tools", {}).items():
        extra = {k: v for k, v in tdata.items() if k not in ("enabled", "timeout", "max_output")}
        tools[tname] = ToolConfig(
            enabled=tdata.get("enabled", True),
            timeout=tdata.get("timeout", 30),
            max_output=tdata.get("max_output", 5000),
            extra=extra,
        )

    skill_data = data.get("skills", {})
    skills = SkillConfig(
        auto_create=skill_data.get("auto_create", True),
        min_tool_calls=skill_data.get("min_tool_calls", 2),
        min_messages=skill_data.get("min_messages", 4),
        auto_evolve=skill_data.get("auto_evolve", True),
        evolve_threshold=skill_data.get("evolve_threshold", 3),
    )

    return ToolsConfig(tools=tools, skills=skills)


# ============================================
# Sandbox Configuration
# ============================================

def load_sandbox_config():
    """Load sandbox configuration from YAML + env vars."""
    from .sandbox.base import SandboxConfig

    data = load_yaml("app.yaml")
    sandbox_data = data.get("sandbox", {})

    return SandboxConfig(
        enabled=sandbox_data.get("enabled", True),
        backend=get_env("SANDBOX_BACKEND", sandbox_data.get("backend", "auto")),
        workspace=get_env("SANDBOX_WORKSPACE", sandbox_data.get("workspace", "./sandbox_workspace")),
        docker_image=get_env("SANDBOX_DOCKER_IMAGE", sandbox_data.get("docker_image", "python:3.11-slim")),
        memory_limit=sandbox_data.get("memory_limit", "512m"),
        cpu_limit=float(sandbox_data.get("cpu_limit", 1.0)),
        timeout=int(sandbox_data.get("timeout", 60)),
        network_disabled=sandbox_data.get("network_disabled", False),
        max_file_size=int(sandbox_data.get("max_file_size", 100_000)),
        readonly_paths=sandbox_data.get("readonly_paths", ["/etc", "/sys", "/proc", "C:\\Windows"]),
        blocked_paths=sandbox_data.get("blocked_paths", ["/etc/shadow", "/etc/passwd", "C:\\Windows\\System32"]),
        blocked_commands=sandbox_data.get("blocked_commands", [
            "rm -rf /", "rm -rf /*", "mkfs", "dd if=",
            "format", "del /s /q C:\\", ":(){ :|:& };:",
            "shutdown", "reboot", "init 0", "init 6",
        ]),
    )


# ============================================
# Global Config Instances
# ============================================

app_config = load_app_config()
providers_config = load_providers_config()
tools_config = load_tools_config()
sandbox_config = load_sandbox_config()
default_provider, default_model = get_default_provider()


def reload_config():
    """Reload all config from files. Call after saving settings."""
    global app_config, providers_config, tools_config, sandbox_config, default_provider, default_model
    load_dotenv(override=True)
    app_config = load_app_config()
    providers_config = load_providers_config()
    tools_config = load_tools_config()
    sandbox_config = load_sandbox_config()
    default_provider, default_model = get_default_provider()
