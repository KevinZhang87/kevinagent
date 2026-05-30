from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # system, user, assistant, tool
    content: str = ""
    tool_calls: list = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list = field(default_factory=list)
    finish_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0  # Tokens served from prompt cache


@dataclass
class LLMStreamChunk:
    delta_content: str = ""
    delta_tool_calls: list = field(default_factory=list)
    finish_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class BaseLLMProvider(ABC):
    """Base class for all LLM providers."""

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    async def chat(self, messages: list[LLMMessage], tools: list[dict] = None) -> LLMResponse:
        """Send a chat completion request."""
        pass

    @abstractmethod
    async def chat_stream(self, messages: list[LLMMessage], tools: list[dict] = None) -> AsyncIterator[LLMStreamChunk]:
        """Send a streaming chat completion request."""
        pass

    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """Format tools to OpenAI-compatible format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]
