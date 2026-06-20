"""DeepSeek V4 LLM provider (OpenAI-compatible API)."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, ToolCall
from likecodex_engine.llm.openai_stream import complete_with_reconnect, stream_openai_chat_with_reconnect

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"


def resolve_api_key(api_key: str | None) -> str | None:
    """Resolve DeepSeek API key from explicit value or environment."""
    if api_key:
        return api_key
    return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LIKECODEX_LLM_API_KEY")


class DeepSeekProvider(LLMProvider):
    """DeepSeek V4 provider with context-cache usage tracking."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
        thinking: bool = False,
    ) -> None:
        resolved_key = resolve_api_key(api_key)
        super().__init__(model, resolved_key, base_url or DEFAULT_BASE_URL)
        self.thinking = thinking
        self.client = AsyncOpenAI(api_key=resolved_key, base_url=self.base_url)

    @staticmethod
    def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            item: dict[str, Any] = {"role": m.role.value, "content": m.content}
            if m.tool_calls:
                item["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                item["tool_call_id"] = m.tool_call_id
            if m.name:
                item["name"] = m.name
            out.append(item)
        return out

    @staticmethod
    def _parse_usage(usage: Any) -> dict[str, int]:
        if usage is None:
            return {}
        result: dict[str, int] = {}
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        ):
            value = getattr(usage, key, None)
            if value is not None:
                result[key] = int(value)
        return result

    def _extra_body(self) -> dict[str, Any]:
        thinking_type = "enabled" if self.thinking else "disabled"
        return {"thinking": {"type": thinking_type}}

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": self._extra_body(),
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        resp = await complete_with_reconnect(lambda: self.client.chat.completions.create(**params))
        choice = resp.choices[0]
        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )
        usage = self._parse_usage(resp.usage)
        if choice.finish_reason:
            usage = {**usage, "finish_reason": choice.finish_reason}
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            model=resp.model,
            usage=self._parse_usage(resp.usage),
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "extra_body": self._extra_body(),
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        async def create_stream():
            return await self.client.chat.completions.create(**params)

        async for event in stream_openai_chat_with_reconnect(
            create_stream,
            model=self.model,
            parse_usage=self._parse_usage,
        ):
            yield event
