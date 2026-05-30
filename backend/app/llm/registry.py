from .base import BaseLLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider
from app.config import providers_config, default_provider, default_model


def get_provider(provider_name: str = "", model: str = "", api_key: str = "") -> BaseLLMProvider:
    """Get a LLM provider instance."""
    provider_name = provider_name or default_provider
    model = model or default_model

    if provider_name not in providers_config:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(providers_config.keys())}")

    config = providers_config[provider_name]
    key = api_key or config.api_key

    if provider_name == "anthropic":
        return AnthropicProvider(api_key=key, model=model)
    elif provider_name == "ollama":
        return OllamaProvider(base_url=config.base_url, model=model)
    else:
        return OpenAIProvider(api_key=key, base_url=config.base_url, model=model)


def get_available_providers() -> list[dict]:
    """Get list of available providers with their configuration status."""
    result = []
    for pid, config in providers_config.items():
        result.append({
            "name": config.name,
            "id": pid,
            "models": [{"id": m.id, "name": m.name} for m in config.models],
            "is_configured": config.is_configured,
        })
    return result
