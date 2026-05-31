from typing import AsyncIterator
from .base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk, cleanup_tool_call_messages
import httpx
import json


class OllamaProvider(BaseLLMProvider):
    """Ollama local model provider."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        super().__init__("", base_url, model)
        self.base_url = base_url.rstrip("/")

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Format messages for Ollama API.

        Ollama requires:
        - tool messages must follow an assistant message with tool_calls
        - ALL tool_calls must have corresponding tool messages
        """
        # First: clean up incomplete tool-call sequences
        messages = cleanup_tool_call_messages(messages)

        # Then: convert to Ollama native API format
        formatted = []
        for m in messages:
            if m.role == "assistant" and m.tool_calls:
                msg = {"role": "assistant", "content": m.content or ""}
                tool_calls = []
                for tc in m.tool_calls:
                    tool_calls.append({
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.loads(tc.get("arguments", "{}")) if isinstance(tc.get("arguments"), str) else tc.get("arguments", {}),
                        },
                    })
                msg["tool_calls"] = tool_calls
                formatted.append(msg)
            elif m.role == "tool":
                formatted.append({
                    "role": "tool",
                    "content": m.content,
                    "tool_call_id": m.tool_call_id,
                })
            else:
                formatted.append({"role": m.role, "content": m.content})
        return formatted

    async def chat(self, messages: list[LLMMessage], tools: list[dict] = None) -> LLMResponse:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": self.model,
                "messages": self._format_messages(messages),
                "stream": False,
            }
            if tools:
                payload["tools"] = self._format_tools(tools)

            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            data = resp.json()

            content = ""
            tool_calls = []
            message = data.get("message", {})
            content = message.get("content", "")
            if message.get("tool_calls"):
                for tc in message["tool_calls"]:
                    tool_calls.append({
                        "id": f"call_{tc['function']['name']}",
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"].get("arguments", {})),
                    })

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason="stop" if data.get("done") else "",
                prompt_tokens=data.get("prompt_eval_count", 0) or 0,
                completion_tokens=data.get("eval_count", 0) or 0,
                total_tokens=(data.get("prompt_eval_count", 0) or 0) + (data.get("eval_count", 0) or 0),
            )

    async def chat_stream(self, messages: list[LLMMessage], tools: list[dict] = None) -> AsyncIterator[LLMStreamChunk]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": self.model,
                "messages": self._format_messages(messages),
                "stream": True,
            }
            if tools:
                payload["tools"] = self._format_tools(tools)

            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    prompt_tokens = data.get("prompt_eval_count", 0) or 0
                    completion_tokens = data.get("eval_count", 0) or 0
                    yield LLMStreamChunk(
                        delta_content=message.get("content", ""),
                        finish_reason="stop" if data.get("done") else "",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                    )
