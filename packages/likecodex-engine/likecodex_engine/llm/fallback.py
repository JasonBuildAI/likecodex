"""Fallback chain – automatically switch to a backup provider on failure."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message
from likecodex_engine.llm.errors import StreamInterruptedError
from likecodex_engine.llm.retry import RetryInfo, notify_provider_retry


def _is_auth_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "401",
            "403",
            "unauthorized",
            "authentication",
            "api key",
            "invalid key",
            "not authenticated",
        )
    )


def _is_rate_limit(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "429",
            "rate limit",
            "rate_limit",
            "too many requests",
            "quota exceeded",
        )
    )


def _is_timeout(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "timeout",
            "timed out",
            "deadline exceeded",
            "connection timeout",
        )
    )


def _is_retryable(exc: BaseException) -> bool:
    return _is_auth_error(exc) or _is_rate_limit(exc) or _is_timeout(exc)


class FallbackChain(LLMProvider):
    """Provider that chains multiple backends and falls through on failure.

    On each retryable error (auth / rate-limit / timeout) the chain moves
    to the next provider in the list.  Non-retryable errors are raised
    immediately.
    """

    def __init__(
        self,
        providers: list[LLMProvider],
        model: str = "",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model, api_key, base_url)
        if not providers:
            raise ValueError("FallbackChain requires at least one provider")
        self._providers = providers
        # Use the model name from the first provider if not explicitly set
        if not model and providers:
            self.model = providers[0].model

    @property
    def active_provider(self) -> LLMProvider:
        return self._providers[0]

    @property
    def providers(self) -> list[LLMProvider]:
        return list(self._providers)

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        last_error: Exception | None = None

        for idx, provider in enumerate(self._providers):
            try:
                return await provider.complete(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc):
                    raise
                notify_provider_retry(
                    RetryInfo(
                        attempt=idx + 1,
                        max_attempts=len(self._providers),
                        error=str(exc),
                        reason="fallback",
                    )
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("FallbackChain exhausted without result")

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        last_error: Exception | None = None

        for idx, provider in enumerate(self._providers):
            try:
                async for event in provider.stream(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield event
                return  # Stream completed successfully
            except Exception as exc:
                last_error = exc
                # StreamInterruptedError means partial output was sent;
                # do NOT fallback in that case since the user already saw output.
                if isinstance(exc, StreamInterruptedError):
                    raise
                if not _is_retryable(exc):
                    raise
                notify_provider_retry(
                    RetryInfo(
                        attempt=idx + 1,
                        max_attempts=len(self._providers),
                        error=str(exc),
                        reason="fallback",
                    )
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("FallbackChain stream exhausted without result")
