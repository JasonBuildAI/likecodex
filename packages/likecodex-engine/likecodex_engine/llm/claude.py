"""Anthropic Claude LLM provider — with thinking mode, image input, and cost tracking."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, Role, ToolCall
from likecodex_engine.llm.anthropic_stream import stream_anthropic_with_reconnect
from likecodex_engine.llm.openai_stream import complete_with_reconnect

# ── Pricing (per 1M tokens, USD) ──────────────────────────────
CLAUDE_PRICING: dict[str, dict[str, float]] = {
    "claude-3-opus-latest": {
        "input": 15.00,
        "output": 75.00,
        "thinking": 18.75,  # thinking tokens charged at output rate
    },
    "claude-3-5-sonnet-latest": {
        "input": 3.00,
        "output": 15.00,
        "thinking": 3.75,
    },
    "claude-3-5-haiku-latest": {
        "input": 0.80,
        "output": 4.00,
        "thinking": 1.00,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
    },
    "claude-3-sonnet-20240229": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
    },
}

DEFAULT_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_MAX_TOKENS = 8192

# Models with extended thinking support
THINKING_CAPABLE_MODELS = {
    "claude-3-opus-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-opus-20240229",
}


def _resolve_api_key(api_key: str | None) -> str:
    if api_key:
        return api_key
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _get_pricing(model: str) -> dict[str, float]:
    """Get pricing for a model, falling back to sonnet pricing."""
    # Try exact match, then prefix match
    if model in CLAUDE_PRICING:
        return CLAUDE_PRICING[model]
    for key, prices in CLAUDE_PRICING.items():
        if model.startswith(key.rstrip("latest").rstrip("-")) or key.startswith(model):
            return prices
    return CLAUDE_PRICING["claude-3-5-sonnet-latest"]


def _calculate_cost(model: str, input_tokens: int, output_tokens: int, thinking_tokens: int = 0) -> float:
    """Calculate USD cost for a Claude API call."""
    prices = _get_pricing(model)
    input_cost = input_tokens / 1_000_000 * prices["input"]
    # Thinking tokens charged at a different rate in some models
    thinking_rate = prices.get("thinking", prices["output"])
    non_thinking = output_tokens - thinking_tokens
    output_cost = non_thinking / 1_000_000 * prices["output"]
    thinking_cost = thinking_tokens / 1_000_000 * thinking_rate
    return round(input_cost + output_cost + thinking_cost, 10)


def _is_thinking_capable(model: str) -> bool:
    for capable in THINKING_CAPABLE_MODELS:
        if model.startswith(capable.rstrip("latest").rstrip("-")) or capable.startswith(model):
            return True
    return False


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider with thinking mode, image input, and cost tracking.

    Supports:
      - Streaming (``stream()``) and non-streaming (``complete()``)
      - Tool / function calling
      - Extended thinking / reasoning mode (Opus / Sonnet)
      - Base64-encoded image input
      - Cost estimation using Claude per-model pricing
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        thinking: bool = False,
        thinking_budget: int | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        super().__init__(model, api_key, base_url)
        key = _resolve_api_key(api_key)
        self.client = AsyncAnthropic(api_key=key, base_url=base_url)
        self.thinking = thinking and _is_thinking_capable(model)
        self.thinking_budget = thinking_budget or (max_tokens // 2)
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    def _to_anthropic_messages(
        self,
        messages: list[Message],
        images: list[dict[str, str]] | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert internal messages to Anthropic wire format.

        Returns ``(system_text, anthropic_messages)``.
        Anthropic separates the system prompt from the message list.
        """
        system: str | None = None
        out: list[dict[str, Any]] = []
        image_idx = 0

        for m in messages:
            if m.role == Role.SYSTEM and system is None:
                system = m.content
                continue

            item: dict[str, Any] = {"role": _map_role(m.role), "content": []}

            # ── Text content ──
            if m.content:
                text_parts: list[dict[str, Any]] = [{"type": "text", "text": m.content}]

                # Inject images after text content if provided
                if images and image_idx < len(images):
                    img = images[image_idx]
                    text_parts.append(self._image_block(img))
                    image_idx += 1

                item["content"].extend(text_parts)

            # ── Tool calls ──
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

            # ── Tool result ──
            if m.role == Role.TOOL and m.tool_call_id:
                item["content"].append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }
                )

            out.append(item)

        # Any remaining images that weren't attached to a specific message
        if images and image_idx < len(images):
            if not out:
                out.append({"role": "user", "content": []})
            remaining = images[image_idx:]
            for img in remaining:
                out[-1]["content"].append(self._image_block(img))

        return system, out

    @staticmethod
    def _image_block(img: dict[str, str]) -> dict[str, Any]:
        """Build an Anthropic image content block from a base64 dict."""
        media_type = img.get("media_type", "image/png")
        data = img.get("data", img.get("base64", ""))
        # If it's a file path, read and encode it
        if data and not _is_base64(data) and Path(data).exists():
            raw = Path(data).read_bytes()
            data = base64.b64encode(raw).decode("utf-8")
            ext = Path(data).suffix.lower()
            media_type = _ext_to_media_type(ext)
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            },
        }

    @staticmethod
    def _to_anthropic_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Convert OpenAI-style tool definitions to Anthropic format."""
        if not tools:
            return None
        anthro_tools: list[dict[str, Any]] = []
        for tool in tools:
            fn = tool.get("function", tool)
            anthro_tools.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                }
            )
        return anthro_tools

    @staticmethod
    def _parse_usage(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        result: dict[str, int] = {
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "input_tokens", 0) or 0)
            + int(getattr(usage, "output_tokens", 0) or 0),
        }
        # Capture thinking tokens if available
        thinking = getattr(usage, "thinking_tokens", None)
        if thinking is not None:
            result["thinking_tokens"] = int(thinking)
        return result

    def _estimate_cost(self, usage: dict[str, int]) -> float:
        """Estimate USD cost from parsed usage."""
        return _calculate_cost(
            model=self.model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            thinking_tokens=usage.get("thinking_tokens", 0),
        )

    # ------------------------------------------------------------------
    # Thinking / reasoning extra body
    # ------------------------------------------------------------------

    def _extra_body(self) -> dict[str, Any]:
        """Build the thinking configuration for the API request body."""
        if not self.thinking:
            return {}
        return {
            "thinking": {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }
        }

    # ------------------------------------------------------------------
    # Public API: complete
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        system, anthro_messages = self._to_anthropic_messages(messages)
        anthro_tools = self._to_anthropic_tools(tools)
        extra = self._extra_body()

        async def _create():
            kwargs: dict[str, Any] = {
                "model": self.model,
                "system": system,
                "messages": anthro_messages,
                "max_tokens": max(max_tokens, self._max_tokens),
                "temperature": temperature,
            }
            if anthro_tools:
                kwargs["tools"] = anthro_tools
            if extra:
                kwargs["extra_body"] = extra
            return await self.client.messages.create(**kwargs)

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
        usage["estimated_cost_usd"] = self._estimate_cost(usage)

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            model=resp.model,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Public API: stream
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        system, anthro_messages = self._to_anthropic_messages(messages)
        anthro_tools = self._to_anthropic_tools(tools)
        extra = self._extra_body()

        async def create_stream():
            kwargs: dict[str, Any] = {
                "model": self.model,
                "system": system,
                "messages": anthro_messages,
                "max_tokens": max(max_tokens, self._max_tokens),
                "temperature": temperature,
                "stream": True,
            }
            if anthro_tools:
                kwargs["tools"] = anthro_tools
            if extra:
                kwargs["extra_body"] = extra
            return await self.client.messages.create(**kwargs)

        # Wrap the parse_usage to inject cost estimate
        def _parse_with_cost(response_or_event: Any) -> dict[str, int]:
            usage = self._parse_usage(response_or_event)
            if usage:
                usage["estimated_cost_usd"] = self._estimate_cost(usage)
            return usage

        async for event in stream_anthropic_with_reconnect(
            create_stream,
            model=self.model,
            parse_usage=_parse_with_cost,
        ):
            yield event

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """Best-effort token count for Claude (approximate)."""
        # Claude uses ~4 chars per token
        return len(text) // 4

    def get_pricing_info(self) -> dict[str, float]:
        """Return the pricing table for the current model."""
        return _get_pricing(self.model)


def _map_role(role: Role) -> str:
    if role == Role.ASSISTANT:
        return "assistant"
    if role == Role.USER:
        return "user"
    if role == Role.TOOL:
        return "user"
    return "user"


def _is_base64(s: str) -> bool:
    """Heuristic: check if a string looks like base64."""
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", s.strip())) and len(s) > 50


def _ext_to_media_type(ext: str) -> str:
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mapping.get(ext.lower(), "image/png")
