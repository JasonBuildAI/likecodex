"""Fallback chain – automatically switch to a backup provider on failure.

Provides:
  - ``FallbackChain`` — provider that chains multiple backends and falls through
  - ``build_fallback_chain`` — convenience builder from config dicts
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message
from likecodex_engine.llm.errors import StreamInterruptedError
from likecodex_engine.llm.factory import create_provider
from likecodex_engine.llm.retry import RetryInfo, notify_provider_retry


# ── Error classifiers ─────────────────────────────────────────

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


def _is_quota(exc: BaseException) -> bool:
    """Check if the error indicates quota exhaustion (retryable with a different provider)."""
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "insufficient_quota",
            "quota",
            "billing",
            "out of credits",
            "credit limit",
            "payment required",
            "402",
        )
    )


def _is_retryable(exc: BaseException) -> bool:
    return _is_auth_error(exc) or _is_rate_limit(exc) or _is_timeout(exc) or _is_quota(exc)


# ── Default fallback chain (provider-name based) ──────────────

DEFAULT_FALLBACK_CHAIN: list[dict[str, Any]] = [
    {"provider": "deepseek", "model": "deepseek-v4-pro"},
    {"provider": "claude", "model": "claude-3-5-sonnet-latest"},
    {"provider": "deepseek", "model": "deepseek-v4-flash"},
    {"provider": "ollama", "model": "llama3.2"},
]


def build_fallback_chain(
    configs: list[dict[str, Any]] | None = None,
) -> FallbackChain:
    """Build a FallbackChain from provider config dicts.

    Each config dict is passed to ``factory.create_provider()``.
    If ``configs`` is ``None``, the ``DEFAULT_FALLBACK_CHAIN`` is used::

        [
            {"provider": "deepseek", "model": "deepseek-v4-pro"},
            {"provider": "claude", "model": "claude-3-5-sonnet-latest"},
            {"provider": "deepseek", "model": "deepseek-v4-flash"},
            {"provider": "ollama", "model": "llama3.2"},
        ]

    Parameters
    ----------
    configs : list[dict] | None
        List of provider config dicts. Each must have at least ``provider`` and ``model``.

    Returns
    -------
    FallbackChain
        A configured fallback chain instance.
    """
    configs = configs or DEFAULT_FALLBACK_CHAIN
    providers: list[LLMProvider] = []
    for cfg in configs:
        providers.append(
            create_provider(
                provider=cfg.get("provider", "deepseek"),
                model=cfg.get("model", "deepseek-v4-flash"),
                api_key=cfg.get("api_key"),
                base_url=cfg.get("base_url"),
                thinking=bool(cfg.get("thinking", False)),
                thinking_budget=cfg.get("thinking_budget"),
                reasoning_effort=str(cfg.get("reasoning_effort", "")),
            )
        )
    return FallbackChain(providers, model=configs[0].get("model", "") if configs else "")


# ── FallbackChain provider ────────────────────────────────────

class FallbackChain(LLMProvider):
    """Provider that chains multiple backends and falls through on failure.

    On each retryable error (auth / rate-limit / timeout / quota) the chain moves
    to the next provider in the list. Non-retryable errors are raised immediately.

    Example::

        # Direct instance approach
        chain = FallbackChain([
            DeepSeekProvider("deepseek-v4-pro"),
            ClaudeProvider("claude-3-5-sonnet-latest"),
            OllamaProvider("llama3.2"),
        ])

        # Config-based approach (recommended)
        chain = build_fallback_chain([
            {"provider": "deepseek", "model": "deepseek-v4-pro"},
            {"provider": "claude", "model": "claude-3-5-sonnet-latest"},
            {"provider": "ollama", "model": "llama3.2"},
        ])
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
        total_providers = len(self._providers)

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
                is_last = idx >= total_providers - 1
                notify_provider_retry(
                    RetryInfo(
                        attempt=idx + 1,
                        max_attempts=total_providers,
                        error=str(exc),
                        reason="fallback",
                    )
                )
                logger.warning(
                    "FallbackChain: provider %d/%d (%s) failed: %s",
                    idx + 1, total_providers,
                    type(provider).__name__,
                    exc,
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
        total_providers = len(self._providers)

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
                is_last = idx >= total_providers - 1
                notify_provider_retry(
                    RetryInfo(
                        attempt=idx + 1,
                        max_attempts=total_providers,
                        error=str(exc),
                        reason="fallback",
                    )
                )
                logger.warning(
                    "FallbackChain stream: provider %d/%d (%s) failed: %s",
                    idx + 1, total_providers,
                    type(provider).__name__,
                    exc,
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("FallbackChain stream exhausted without result")


import logging

logger = logging.getLogger(__name__)
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
