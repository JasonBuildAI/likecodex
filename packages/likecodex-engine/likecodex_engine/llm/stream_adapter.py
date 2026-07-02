"""StreamAdapter – normalise streaming events from different providers into a
unified format.

Each provider (OpenAI, Anthropic, Gemini) emits streaming events with
different shapes.  ``StreamAdapter`` wraps any provider and yields
``LLMResponse`` instances with a consistent ``event_type`` vocabulary:

+------------------+--------------------------------------------------+
| event_type       | meaning                                          |
+------------------+--------------------------------------------------+
| ``delta``        | A new text token / fragment                      |
| ``reasoning``    | Reasoning / thinking token (DeepSeek, some local) |
| ``tool_dispatch``| Tool call started (partial)                      |
| ``assistant``    | Final aggregated assistant message (with usage)  |
| ``retrying``     | Reconnect / fallback notification                |
+------------------+--------------------------------------------------+
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message


class StreamAdapter(LLMProvider):
    """Wraps an LLMProvider and normalises its stream output.

    In most cases the underlying providers (OpenAI, Anthropic, Gemini)
    already emit ``LLMResponse`` with sensible ``event_type`` values.
    This adapter exists to:

    * Guarantee that every event has a known ``event_type``.
    * Inject a ``reasoning`` event type bridge for providers that output
      reasoning in a ``delta`` event (by checking for ``reasoning_content``
      in the response).
    * Provide a single point for future normalisation logic.
    """

    def __init__(
        self,
        provider: LLMProvider,
        model: str = "",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model or provider.model, api_key, base_url)
        self._provider = provider

    # ------------------------------------------------------------------
    # Non-streaming pass-through
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return await self._provider.complete(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ------------------------------------------------------------------
    # Normalised streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        async for event in self._provider.stream(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield self._normalise(event)

    @staticmethod
    def _normalise(event: LLMResponse) -> LLMResponse:
        """Ensure every event has a proper ``event_type``.

        Heuristics applied:
          * If ``reasoning_content`` is set and ``event_type`` is ``delta``,
            flip the type to ``reasoning``.
          * If ``event_type`` is empty / unknown, default to ``delta`` when
            content is present, or ``assistant`` otherwise.
        """
        event_type = event.event_type or ""

        # Detect reasoning content that slipped through as a delta
        if event_type == "delta" and event.reasoning_content:
            event.event_type = "reasoning"
            return event

        # Unknown event_type → infer from content
        if event_type not in {
            "delta",
            "reasoning",
            "tool_dispatch",
            "assistant",
            "tool_result",
            "permission",
            "error",
            "plan",
            "retrying",
        }:
            if event.content:
                event.event_type = "delta"
            else:
                event.event_type = "assistant"

        return event
