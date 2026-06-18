"""Anthropic Claude LLM provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, Role, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None) -> None:
        super().__init__(model, api_key, base_url)
        self.client = AsyncAnthropic(api_key=api_key, base_url=base_url)

    @staticmethod
    def _to_anthropic_messages(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        system: str | None = None
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == Role.SYSTEM:
                system = (system or "") + m.content + "\n"
                continue
            item: dict[str, Any] = {"role": m.role.value, "content": m.content}
            if m.tool_calls:
                item["content"] = [{"type": "text", "text": m.content or ""}]
                item["content"].extend(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": __import__("json").loads(tc["function"]["arguments"]),
                    }
                    for tc in m.tool_calls
                )
            if m.tool_call_id:
                item["role"] = "user"
                item["content"] = [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }
                ]
            out.append(item)
        return system, out

    @staticmethod
    def _to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        system, msgs = self._to_anthropic_messages(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = self._to_anthropic_tools(tools)

        resp = await self.client.messages.create(**params)
        content_text = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input),
                    )
                )
        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            model=resp.model,
            usage={
                "prompt_tokens": resp.usage.input_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.output_tokens if resp.usage else 0,
            },
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        system, msgs = self._to_anthropic_messages(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = self._to_anthropic_tools(tools)

        async for event in self.client.messages.create(**params):
            if event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield LLMResponse(content=delta.text)
