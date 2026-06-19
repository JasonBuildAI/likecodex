"""OpenAI-compatible LLM provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, ToolCall
from likecodex_engine.llm.openai_stream import complete_with_reconnect, stream_openai_chat_with_reconnect


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None) -> None:
        super().__init__(model, api_key, base_url)
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

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
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

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
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        resp = await complete_with_reconnect(
            lambda: self.client.chat.completions.create(**params)
        )
        choice = resp.choices[0]
        tool_calls = []
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
            usage=usage,
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
