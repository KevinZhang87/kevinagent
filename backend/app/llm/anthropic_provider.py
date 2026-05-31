import json
from typing import AsyncIterator
from .base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk, cleanup_tool_call_messages


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        super().__init__(api_key, "", model)

    async def _get_client(self):
        import anthropic
        return anthropic.AsyncAnthropic(api_key=self.api_key)

    def _format_messages(self, messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        """Format messages for Anthropic API. Returns (system_msg, chat_messages).

        Anthropic requires:
        - Messages must alternate between user and assistant roles
        - An assistant with tool_use blocks must be followed by user message(s)
          with tool_result blocks for ALL tool_use IDs
        - The first message must be a user message
        """
        # First: clean up incomplete tool-call sequences (shared across all providers)
        messages = cleanup_tool_call_messages(messages)

        # Extract system message + convert to Anthropic format
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            elif m.role == "tool":
                # Anthropic requires tool_results in a USER role message.
                # Merge consecutive tool messages into a single user message
                # to follow Anthropic's canonical format.
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content,
                }
                # Check if the previous message is also a user with tool_results
                if chat_messages and chat_messages[-1]["role"] == "user":
                    prev_content = chat_messages[-1]["content"]
                    if isinstance(prev_content, list) and prev_content and prev_content[0].get("type") == "tool_result":
                        # Merge into the previous user message's tool_result blocks
                        prev_content.append(tool_result_block)
                        continue
                # Otherwise, start a new user message
                chat_messages.append({
                    "role": "user",
                    "content": [tool_result_block],
                })
            elif m.role == "assistant" and m.tool_calls:
                content_blocks = []
                if m.content:
                    content_blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "input": json.loads(tc.get("arguments", "{}")) if isinstance(tc.get("arguments"), str) else tc.get("arguments", {}),
                    })
                chat_messages.append({"role": "assistant", "content": content_blocks})
            else:
                chat_messages.append({"role": m.role, "content": m.content})
        return system_msg, chat_messages

    async def chat(self, messages: list[LLMMessage], tools: list[dict] = None) -> LLMResponse:
        client = await self._get_client()

        system_msg, chat_messages = self._format_messages(messages)

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": chat_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = [
                {"name": t["name"], "description": t.get("description", ""), "input_schema": t.get("parameters", {"type": "object", "properties": {}})}
                for t in tools
            ]

        response = await client.messages.create(**kwargs)

        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                import json
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": json.dumps(block.input),
                })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "",
            prompt_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            completion_tokens=getattr(response.usage, "output_tokens", 0) or 0,
            total_tokens=(getattr(response.usage, "input_tokens", 0) or 0) + (getattr(response.usage, "output_tokens", 0) or 0),
        )

    async def chat_stream(self, messages: list[LLMMessage], tools: list[dict] = None) -> AsyncIterator[LLMStreamChunk]:
        client = await self._get_client()

        system_msg, chat_messages = self._format_messages(messages)

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": chat_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if tools:
            kwargs["tools"] = [
                {"name": t["name"], "description": t.get("description", ""), "input_schema": t.get("parameters", {"type": "object", "properties": {}})}
                for t in tools
            ]

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield LLMStreamChunk(delta_content=text)

            # Get usage from the final message
            final_message = await stream.get_final_message()
            input_tokens = getattr(final_message.usage, "input_tokens", 0) or 0
            output_tokens = getattr(final_message.usage, "output_tokens", 0) or 0
            yield LLMStreamChunk(
                delta_content="",
                finish_reason="stop",
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            )
