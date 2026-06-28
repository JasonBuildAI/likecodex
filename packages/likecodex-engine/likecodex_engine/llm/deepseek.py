"""DeepSeek V4 LLM provider (OpenAI-compatible API)."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
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


# ── Cost tracking ──────────────────────────────────────────────

DS_FLASH_INPUT = 0.15 / 1_000_000  # $ per token
DS_FLASH_OUTPUT = 0.60 / 1_000_000
DS_PRO_INPUT = 1.00 / 1_000_000
DS_PRO_OUTPUT = 4.00 / 1_000_000
DS_CACHE_HIT_DISCOUNT = 0.10  # ~90% cheaper for cached prefix tokens


@dataclass
class DeepSeekUsage:
    """Token usage breakdown with DeepSeek-specific cost calculation."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    reasoning_tokens: int = 0
    model: str = "deepseek-v4-flash"

    @property
    def cache_hit_rate(self) -> float:
        if self.prompt_tokens == 0:
            return 0.0
        hit = self.cache_hit_tokens + self.cache_miss_tokens
        return (self.cache_hit_tokens / hit) if hit > 0 else 0.0

    @property
    def input_cost(self) -> float:
        """Calculate input cost accounting for cache hit discount."""
        is_pro = "pro" in self.model.lower()
        full_price = DS_PRO_INPUT if is_pro else DS_FLASH_INPUT
        # Cache-miss tokens pay full price
        miss_cost = self.cache_miss_tokens * full_price
        # Cache-hit tokens get ~90% discount
        hit_cost = self.cache_hit_tokens * full_price * DS_CACHE_HIT_DISCOUNT
        return miss_cost + hit_cost

    @property
    def output_cost(self) -> float:
        is_pro = "pro" in self.model.lower()
        return self.completion_tokens * (DS_PRO_OUTPUT if is_pro else DS_FLASH_OUTPUT)

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost

    @classmethod
    def from_api_usage(cls, usage: dict[str, int] | None, model: str = "deepseek-v4-flash") -> DeepSeekUsage:
        """Build from the usage dict returned by the DeepSeek API."""
        if not usage:
            return cls(model=model)
        return cls(
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            cache_hit_tokens=int(usage.get("prompt_cache_hit_tokens", 0)),
            cache_miss_tokens=int(usage.get("prompt_cache_miss_tokens", 0)),
            reasoning_tokens=int(usage.get("reasoning_tokens", 0)),
            model=model,
        )


# ── Provider config templates ──────────────────────────────────


@dataclass
class DeepSeekProviderConfig:
    """DeepSeek-specific provider configuration for different modes."""

    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    thinking: bool = False
    reasoning_effort: str = ""
    max_tokens: int = 16_384
    temperature: float = 0.0

    @classmethod
    def flash_default(cls) -> DeepSeekProviderConfig:
        """Fast, cost-effective mode for routine tasks."""
        return cls(
            model="deepseek-v4-flash",
            thinking=False,
            max_tokens=8_192,
            temperature=0.0,
        )

    @classmethod
    def pro_default(cls) -> DeepSeekProviderConfig:
        """Deep reasoning mode for complex architecture/refactoring."""
        return cls(
            model="deepseek-v4-pro",
            thinking=True,
            reasoning_effort="high",
            max_tokens=32_768,
            temperature=0.0,
        )

    @classmethod
    def pro_light(cls) -> DeepSeekProviderConfig:
        """Pro model without thinking, for mid-complexity tasks."""
        return cls(
            model="deepseek-v4-pro",
            thinking=False,
            max_tokens=16_384,
            temperature=0.0,
        )


class DeepSeekProvider(LLMProvider):
    """DeepSeek V4 provider with context-cache usage tracking."""

    _system_prompt: str | None = None

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
        thinking: bool = False,
        reasoning_effort: str = "",
    ) -> None:
        resolved_key = resolve_api_key(api_key)
        super().__init__(model, resolved_key, base_url or DEFAULT_BASE_URL)
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort
        self.client = AsyncOpenAI(api_key=resolved_key, base_url=self.base_url)

    @staticmethod
    def load_system_prompt() -> str:
        """Load the DeepSeek V4 optimized system prompt."""
        if DeepSeekProvider._system_prompt is not None:
            return DeepSeekProvider._system_prompt
        prompt_path = Path(__file__).parent.parent / "prompts" / "deepseek_v4_system.txt"
        if prompt_path.exists():
            DeepSeekProvider._system_prompt = prompt_path.read_text(encoding="utf-8")
        else:
            DeepSeekProvider._system_prompt = ""
        return DeepSeekProvider._system_prompt

    def _to_openai_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert internal messages to OpenAI wire format.

        Reasonix rule: only round-trip reasoning_content on assistant turns that
        carry tool_calls. Pure-text assistant turns must NOT re-emit
        reasoning_content (avoids cache invalidation and API 400s).
        """
        out: list[dict[str, Any]] = []
        for m in messages:
            item: dict[str, Any] = {"role": m.role.value, "content": m.content}
            if m.tool_calls:
                item["tool_calls"] = m.tool_calls
                # Reasonix rule: round-trip reasoning_content only on tool-call turns
                if m.reasoning_content:
                    item["reasoning_content"] = m.reasoning_content
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
        # Also capture reasoning tokens if present
        details = getattr(usage, "completion_tokens_details", None)
        if details is not None:
            reasoning = getattr(details, "reasoning_tokens", None)
            if reasoning is not None:
                result["reasoning_tokens"] = int(reasoning)
        return result

    def _extra_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if self.thinking:
            body["thinking"] = {"type": "enabled"}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return body

    def _build_params(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            **({"stream": True, "stream_options": {"include_usage": True}} if stream else {}),
            "extra_body": self._extra_body(),
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        return params

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        params = self._build_params(messages, tools, temperature, max_tokens)

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
        reasoning_content = getattr(choice.message, "reasoning_content", None) or ""
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            model=resp.model,
            usage=usage,
            reasoning_content=reasoning_content or None,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        params = self._build_params(messages, tools, temperature, max_tokens, stream=True)

        async def create_stream():
            return await self.client.chat.completions.create(**params)

        async for event in stream_openai_chat_with_reconnect(
            create_stream,
            model=self.model,
            parse_usage=self._parse_usage,
        ):
            yield event
