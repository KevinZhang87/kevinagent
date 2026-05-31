from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import yaml
import logging

from app.llm.registry import get_available_providers
from app.config import CONFIG_DIR, reload_config
import app.config as cfg

logger = logging.getLogger("kevin_agent.models")

router = APIRouter(prefix="/api/models", tags=["models"])

BACKEND_DIR = Path(__file__).parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"
APP_YAML = CONFIG_DIR / "app.yaml"
PROVIDERS_YAML = CONFIG_DIR / "providers.yaml"


class SettingsSaveRequest(BaseModel):
    api_keys: dict[str, str] = {}
    base_urls: dict[str, str] = {}
    default_provider: str = ""
    default_model: str = ""
    max_iterations: int = 30
    active_providers: list[str] = []
    custom_models: dict[str, list[dict]] = {}  # provider_id -> [{id, name, max_tokens}]


def update_env_file(updates: dict[str, str]):
    """Update .env file with new key-value pairs."""
    lines = []
    existing_keys = set()
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys.add(key)
                    if key in updates:
                        lines.append(f"{key}={updates[key]}\n")
                        del updates[key]
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
    for key, value in updates.items():
        if key not in existing_keys:
            lines.append(f"{key}={value}\n")
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)
    logger.info("Updated .env file with %d keys", len(existing_keys))


def update_providers_yaml(dp: str, dm: str, base_urls: dict[str, str], custom_models: dict[str, list[dict]] = None):
    """Update providers.yaml with new default provider, model, base URLs, and custom models."""
    data = {}
    if PROVIDERS_YAML.exists():
        with open(PROVIDERS_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    # Update defaults - if both are empty, remove the defaults section
    # so the system will auto-detect from configured providers
    if dp and dm:
        if "defaults" not in data:
            data["defaults"] = {}
        data["defaults"]["provider"] = dp
        data["defaults"]["model"] = dm
    else:
        # Clear defaults to enable auto-detection
        data.pop("defaults", None)

    for pid, url in base_urls.items():
        if url and pid in data.get("providers", {}):
            data["providers"][pid]["base_url"] = url

    # Update custom models
    if custom_models:
        for pid, models in custom_models.items():
            if pid in data.get("providers", {}):
                # Merge: keep existing models, add/update with custom ones
                existing_ids = {m["id"] for m in data["providers"][pid].get("models", [])}
                for m in models:
                    if m["id"] not in existing_ids:
                        data["providers"][pid].setdefault("models", []).append({
                            "id": m["id"],
                            "name": m.get("name", m["id"]),
                            "max_tokens": m.get("max_tokens", 4096),
                        })
                    else:
                        # Update existing model name if provided
                        for em in data["providers"][pid]["models"]:
                            if em["id"] == m["id"] and m.get("name"):
                                em["name"] = m["name"]

    with open(PROVIDERS_YAML, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    logger.info("Updated providers.yaml: default=%s/%s", dp or "(auto)", dm or "(auto)")


def update_app_yaml(max_iter: int, active: list[str] = None):
    """Update app.yaml with max iterations and active providers."""
    data = {}
    if APP_YAML.exists():
        with open(APP_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    if "agent" not in data:
        data["agent"] = {}
    data["agent"]["max_iterations"] = max_iter
    if active is not None:
        data["active_providers"] = active
    with open(APP_YAML, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    logger.info("Updated app.yaml: max_iter=%d active=%s", max_iter, active)


@router.get("/providers")
async def list_providers():
    """List all available LLM providers."""
    return {"providers": get_available_providers()}


@router.get("/providers/{provider_id}/models")
async def list_models(provider_id: str):
    """List models for a specific provider."""
    if provider_id not in cfg.providers_config:
        return {"error": f"Unknown provider: {provider_id}"}
    p = cfg.providers_config[provider_id]
    return {"models": [{"id": m.id, "name": m.name, "max_tokens": m.max_tokens} for m in p.models]}


@router.post("/providers/{provider_id}/models")
async def add_custom_model(provider_id: str, model_id: str, model_name: str = "", max_tokens: int = 4096):
    """Add a custom model to a provider."""
    if provider_id not in cfg.providers_config:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

    model_name = model_name or model_id
    # Update providers.yaml
    data = {}
    if PROVIDERS_YAML.exists():
        with open(PROVIDERS_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    if provider_id in data.get("providers", {}):
        existing_ids = {m["id"] for m in data["providers"][provider_id].get("models", [])}
        if model_id not in existing_ids:
            data["providers"][provider_id].setdefault("models", []).append({
                "id": model_id,
                "name": model_name,
                "max_tokens": max_tokens,
            })
            with open(PROVIDERS_YAML, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            reload_config()
            logger.info("Custom model added: %s/%s", provider_id, model_id)
            return {"status": "ok", "message": f"Model {model_id} added to {provider_id}"}
        else:
            return {"status": "ok", "message": f"Model {model_id} already exists"}

    raise HTTPException(status_code=404, detail="Provider not found in config")


@router.delete("/providers/{provider_id}/models/{model_id}")
async def remove_custom_model(provider_id: str, model_id: str):
    """Remove a custom model from a provider."""
    data = {}
    if PROVIDERS_YAML.exists():
        with open(PROVIDERS_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    if provider_id in data.get("providers", {}):
        models = data["providers"][provider_id].get("models", [])
        original_len = len(models)
        data["providers"][provider_id]["models"] = [m for m in models if m["id"] != model_id]
        if len(data["providers"][provider_id]["models"]) < original_len:
            with open(PROVIDERS_YAML, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            reload_config()
            logger.info("Custom model removed: %s/%s", provider_id, model_id)
            return {"status": "ok", "message": f"Model {model_id} removed"}

    raise HTTPException(status_code=404, detail="Model not found")


@router.get("/current")
async def get_current_config():
    """Get current configuration."""
    return {
        "provider": cfg.default_provider,
        "model": cfg.default_model,
        "active_providers": cfg.app_config.active_providers,
        "providers": {
            pid: {"base_url": p.base_url, "is_configured": p.is_configured}
            for pid, p in cfg.providers_config.items()
        },
        "auto_detected": not (cfg.get_env("DEFAULT_PROVIDER") and cfg.get_env("DEFAULT_MODEL")),
    }


@router.post("/settings/save")
async def save_settings(request: SettingsSaveRequest):
    """Save settings and reload configuration."""
    try:
        logger.info("Saving settings: default=%s/%s active=%s",
                     request.default_provider, request.default_model, request.active_providers)

        # Update .env file with API keys
        env_updates = {}
        key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
            "glm": "GLM_API_KEY",
            "mimo": "MIMO_API_KEY",
        }
        for pid, key in request.api_keys.items():
            env_key = key_map.get(pid)
            if env_key and key:
                env_updates[env_key] = key
        if env_updates:
            update_env_file(env_updates)

        # Update providers config
        # If default_provider is empty, clear the defaults in providers.yaml
        # so the system will auto-detect from configured providers
        update_providers_yaml(
            request.default_provider,
            request.default_model,
            request.base_urls,
            request.custom_models or None,
        )

        # Update app config
        update_app_yaml(request.max_iterations, request.active_providers or None)

        # Reload configuration
        reload_config()

        logger.info("Settings saved successfully")
        return {"status": "ok", "message": "Settings saved and reloaded successfully"}
    except Exception as e:
        logger.error("Failed to save settings: %s", e)
        return {"status": "error", "message": str(e)}
