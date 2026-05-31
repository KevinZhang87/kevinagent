from typing import AsyncIterator
from openai import AsyncOpenAI
from .base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk, cleanup_tool_call_messages


class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible provider (works with OpenAI, DeepSeek, Moonshot, GLM, etc.)"""

    def __init__(self, api_key: str, base_url: str = "", model: str = "gpt-4o"):
        super().__init__(api_key, base_url, model)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Format LLMMessage list to OpenAI API message format.

        DeepSeek, MiMo, Moonshot, GLM and other strict providers require:
        - tool messages must follow an assistant message with tool_calls
        - ALL tool_calls must have corresponding tool messages
        - orphan tool messages are dropped

        Note: tool_calls in DB are stored as [{"id", "name", "arguments"}]
        but OpenAI API expects [{"id", "type", "function": {"name", "arguments"}}]
        """
        # First: clean up incomplete tool-call sequences (shared across all providers)
        messages = cleanup_tool_call_messages(messages)

        # Then: convert to OpenAI API format
        raw_formatted = []
        for m in messages:
            msg = {"role": m.role}
            if m.role == "assistant" and m.tool_calls:
                msg["content"] = m.content or None
                formatted_tool_calls = []
                for tc in m.tool_calls:
                    if "function" in tc:
                        formatted_tool_calls.append(tc)
                    else:
                        formatted_tool_calls.append({
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": tc.get("arguments", "{}"),
                            },
                        })
                msg["tool_calls"] = formatted_tool_calls
            elif m.role == "tool":
                msg["content"] = m.content
                msg["tool_call_id"] = m.tool_call_id
            else:
                msg["content"] = m.content
            raw_formatted.append(msg)

        return raw_formatted

    async def chat(self, messages: list[LLMMessage], tools: list[dict] = None) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": self._format_messages(messages),
        }
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })

        # Track cached tokens if available (OpenAI prompt caching)
        cached_tokens = getattr(response.usage, "prompt_tokens_details", None)
        cached_count = getattr(cached_tokens, "cached_tokens", 0) if cached_tokens else 0

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "",
            prompt_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(response.usage, "total_tokens", 0) or 0,
            cached_tokens=cached_count,
        )

    async def chat_stream(self, messages: list[LLMMessage], tools: list[dict] = None) -> AsyncIterator[LLMStreamChunk]:
        kwargs = {
            "model": self.model,
            "messages": self._format_messages(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if not chunk.choices and chunk.usage:
                # Final chunk with usage info (no content delta)
                yield LLMStreamChunk(
                    delta_content="",
                    finish_reason="stop",
                    prompt_tokens=getattr(chunk.usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(chunk.usage, "completion_tokens", 0) or 0,
                    total_tokens=getattr(chunk.usage, "total_tokens", 0) or 0,
                )
                continue

            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            tool_calls = []
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    tool_calls.append({
                        "index": tc.index,
                        "id": tc.id or "",
                        "name": tc.function.name if tc.function and tc.function.name else "",
                        "arguments": tc.function.arguments if tc.function and tc.function.arguments else "",
                    })

            yield LLMStreamChunk(
                delta_content=delta.content or "",
                delta_tool_calls=tool_calls,
                finish_reason=chunk.choices[0].finish_reason or "",
            )
