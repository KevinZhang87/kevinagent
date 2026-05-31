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


def cleanup_tool_call_messages(messages: list[LLMMessage]) -> list[LLMMessage]:
    """Clean up LLMMessage list to ensure valid tool-call/tool-result sequences.

    Strict providers (DeepSeek, MiMo, Moonshot, GLM, Anthropic, Ollama) require:
    - Every assistant message with tool_calls must be followed by tool messages
      responding to EACH tool_call_id before any non-tool message.
    - Orphan tool messages (no matching tool_call) are dropped.
    - Incomplete assistant tool_calls (missing some results) are removed entirely.

    This should be called BEFORE provider-specific _format_messages() to ensure
    all messages sent to the API are valid.
    """
    cleaned: list[LLMMessage] = []
    pending_tool_call_ids: set[str] = set()
    pending_assistant_idx: int = -1

    def _remove_incomplete():
        nonlocal pending_tool_call_ids, pending_assistant_idx
        if pending_assistant_idx >= 0 and pending_tool_call_ids:
            del cleaned[pending_assistant_idx:]
        pending_tool_call_ids.clear()
        pending_assistant_idx = -1

    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            # New assistant with tool_calls: clean up any previous incomplete one first
            _remove_incomplete()

            cleaned.append(m)
            pending_tool_call_ids = {tc.get("id", "") for tc in m.tool_calls if tc.get("id")}
            pending_assistant_idx = len(cleaned) - 1

        elif m.role == "tool":
            if m.tool_call_id and m.tool_call_id in pending_tool_call_ids:
                cleaned.append(m)
                pending_tool_call_ids.discard(m.tool_call_id)
                if not pending_tool_call_ids:
                    pending_assistant_idx = -1
            # else: skip orphan tool message

        else:
            # Non-tool message: clean up any incomplete tool_calls before appending
            _remove_incomplete()
            cleaned.append(m)

    # Final: remove any trailing incomplete assistant
    _remove_incomplete()

    return cleaned


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
