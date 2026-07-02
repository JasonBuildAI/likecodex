"""Anthropic Claude LLM provider."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, Role, ToolCall
from likecodex_engine.llm.anthropic_stream import stream_anthropic_with_reconnect
from likecodex_engine.llm.openai_stream import complete_with_reconnect


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model, api_key, base_url)
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = AsyncAnthropic(api_key=key, base_url=base_url)

    # ------------------------------------------------------------------
    # Message conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_anthropic_messages(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert internal messages to Anthropic format.

        Returns (system_text, anthropic_messages).
        Anthropic treats the first system message separately.
        """
        system: str | None = None
        out: list[dict[str, Any]] = []

        for m in messages:
            if m.role == Role.SYSTEM and system is None:
                system = m.content
                continue

            item: dict[str, Any] = {"role": _map_role(m.role), "content": []}

            if m.content:
                item["content"].append({"type": "text", "text": m.content})

            if m.tool_calls:
                for tc in m.tool_calls:
                    item["content"].append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": tc.get("function", {}).get("name", ""),
                            "input": json.loads(tc.get("function", {}).get("arguments", "{}"))
                            if isinstance(tc.get("function", {}).get("arguments"), str)
                            else tc.get("function", {}).get("arguments", {}),
                        }
                    )

            if m.role == Role.TOOL and m.tool_call_id:
                item["content"].append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }
                )

            out.append(item)

        return system, out

    @staticmethod
    def _to_openai_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Convert OpenAI-style tool definitions to Anthropic format."""
        if not tools:
            return None

        anthropic_tools: list[dict[str, Any]] = []
        for tool in tools:
            fn = tool.get("function", tool)
            anthropic_tools.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                }
            )
        return anthropic_tools

    @staticmethod
    def _parse_usage(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        return {
            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
            "total_tokens": (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "output_tokens", 0) or 0),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        system, anthro_messages = self._to_anthropic_messages(messages)
        anthro_tools = self._to_openai_tools(tools)

        async def _create():
            return await self.client.messages.create(
                model=self.model,
                system=system,
                messages=anthro_messages,
                tools=anthro_tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        resp = await complete_with_reconnect(_create)

        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in resp.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input) if isinstance(block.input, dict) else {},
                    )
                )

        usage = self._parse_usage(resp)
        if resp.stop_reason:
            usage["finish_reason"] = resp.stop_reason

        return LLMResponse(
            content="".join(content_parts),
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
        system, anthro_messages = self._to_anthropic_messages(messages)
        anthro_tools = self._to_openai_tools(tools)

        async def create_stream():
            return await self.client.messages.create(
                model=self.model,
                system=system,
                messages=anthro_messages,
                tools=anthro_tools,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )

        async for event in stream_anthropic_with_reconnect(
            create_stream,
            model=self.model,
            parse_usage=self._parse_usage,
        ):
            yield event


def _map_role(role: Role) -> str:
    if role == Role.ASSISTANT:
        return "assistant"
    if role == Role.USER:
        return "user"
    if role == Role.TOOL:
        return "user"
    return "user"
