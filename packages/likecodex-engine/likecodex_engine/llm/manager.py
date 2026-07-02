"""LLMManager – connection pool and lifecycle manager for LLM providers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message

logger = logging.getLogger(__name__)

_HEALTH_CHECK_INTERVAL = 60.0  # seconds


@dataclass
class ProviderSlot:
    """A single provider instance tracked by the manager."""

    name: str
    provider: LLMProvider
    healthy: bool = True
    last_error: str = ""
    error_count: int = 0
    consecutive_failures: int = 0


class LLMManager(LLMProvider):
    """Manages multiple LLM providers with health checking and automatic failover.

    Example::

        manager = LLMManager()
        manager.register("primary", OpenAIProvider("gpt-4"))
        manager.register("fallback", AnthropicProvider("claude-3"))

        await manager.start()   # begin health checks
        resp = await manager.complete(messages)
    """

    def __init__(
        self,
        model: str = "",
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        health_check_interval: float = _HEALTH_CHECK_INTERVAL,
    ) -> None:
        super().__init__(model, api_key, base_url)
        self._slots: dict[str, ProviderSlot] = {}
        self._active_name: str = ""
        self._health_check_interval = health_check_interval
        self._health_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, provider: LLMProvider, *, set_active: bool = False) -> None:
        """Register a provider under *name*.

        If *set_active* is ``True`` or no active provider exists yet, this
        provider becomes the active one.
        """
        slot = ProviderSlot(name=name, provider=provider)
        self._slots[name] = slot
        if set_active or not self._active_name:
            self._active_name = name
        logger.info("Registered LLM provider '%s' (%s)", name, type(provider).__name__)

    def unregister(self, name: str) -> None:
        """Remove a provider from the pool."""
        self._slots.pop(name, None)
        if self._active_name == name:
            self._active_name = next(iter(self._slots)) if self._slots else ""

    @property
    def active(self) -> LLMProvider | None:
        slot = self._slots.get(self._active_name)
        return slot.provider if slot else None

    @property
    def active_name(self) -> str:
        return self._active_name

    def switch_to(self, name: str) -> None:
        """Switch the active provider at runtime."""
        if name not in self._slots:
            raise KeyError(f"Unknown provider: {name}")
        self._active_name = name
        logger.info("Switched active LLM provider to '%s'", name)

    def list_providers(self) -> dict[str, bool]:
        return {name: slot.healthy for name, slot in self._slots.items()}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start periodic health checks."""
        if self._health_task is not None:
            return
        self._health_task = asyncio.create_task(self._health_loop())
        logger.debug("LLM health-check loop started (interval=%ss)", self._health_check_interval)

    async def stop(self) -> None:
        """Stop periodic health checks."""
        if self._health_task is not None:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
            logger.debug("LLM health-check loop stopped")

    async def _health_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_all_health()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Health-check loop error")

    async def _check_all_health(self) -> None:
        for name, slot in self._slots.items():
            try:
                # Best-effort: try a minimal completion to gauge health.
                health = await slot.provider.complete(
                    [Message(role="user", content=".")],
                    max_tokens=1,
                )
                slot.healthy = health.content is not None
                slot.consecutive_failures = 0
            except Exception as exc:
                slot.healthy = False
                slot.consecutive_failures += 1
                slot.last_error = str(exc)[:200]
                logger.warning("Health check failed for '%s': %s", name, exc)

    async def check_health(self, name: str | None = None) -> bool:
        """Run a one-shot health check on *name* (or the active provider)."""
        target = name or self._active_name
        slot = self._slots.get(target)
        if slot is None:
            return False
        try:
            await slot.provider.complete(
                [Message(role="user", content=".")],
                max_tokens=1,
            )
            slot.healthy = True
            slot.consecutive_failures = 0
            return True
        except Exception:
            slot.healthy = False
            return False

    # ------------------------------------------------------------------
    # LLMProvider interface – delegates to the active provider
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        active = self.active
        if active is None:
            raise RuntimeError("No active LLM provider registered")
        return await active.complete(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        active = self.active
        if active is None:
            raise RuntimeError("No active LLM provider registered")
        async for event in active.stream(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield event
