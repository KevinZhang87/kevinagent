from .base import BaseLLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider
import app.config as cfg
import logging

logger = logging.getLogger("kevin_agent.llm.registry")


def get_provider(provider_name: str = "", model: str = "", api_key: str = "") -> BaseLLMProvider:
    """Get a LLM provider instance.

    Uses cfg.providers_config / cfg.default_provider / cfg.default_model
    via module-level access (not direct import) so that reload_config()
    updates are reflected immediately.
    """
    provider_name = provider_name or cfg.default_provider
    model = model or cfg.default_model

    if not provider_name:
        raise ValueError("No provider configured. Please configure a provider in Settings.")

    if provider_name not in cfg.providers_config:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(cfg.providers_config.keys())}")

    config = cfg.providers_config[provider_name]
    key = api_key or config.api_key

    # Debug: log key source (mask the key for security)
    masked_key = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
    logger.info("get_provider: provider=%s model=%s base_url=%s key_source=%s key=%s",
                provider_name, model, config.base_url,
                "param" if api_key else f"env({config.id}_API_KEY)",
                masked_key)

    if provider_name == "anthropic":
        return AnthropicProvider(api_key=key, model=model)
    elif provider_name == "ollama":
        return OllamaProvider(base_url=config.base_url, model=model)
    else:
        return OpenAIProvider(api_key=key, base_url=config.base_url, model=model)


def get_available_providers() -> list[dict]:
    """Get list of available providers with their configuration status.

    Uses cfg.providers_config via module-level access so that
    reload_config() updates are reflected immediately.
    """
    result = []
    for pid, config in cfg.providers_config.items():
        result.append({
            "name": config.name,
            "id": pid,
            "models": [{"id": m.id, "name": m.name} for m in config.models],
            "is_configured": config.is_configured,
        })
    return result
