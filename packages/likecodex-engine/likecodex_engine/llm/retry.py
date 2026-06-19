"""Provider retry notification uses a fresh list per context."""

from __future__ import annotations

import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from likecodex_engine.llm.base import LLMResponse

_pending: contextvars.ContextVar[list[LLMResponse] | None] = contextvars.ContextVar(
    "likecodex_retry_pending",
    default=None,
)


@dataclass
class RetryInfo:
    attempt: int
    max_attempts: int
    error: str
    reason: str = "provider"


def _pending_list() -> list[LLMResponse]:
    pending = _pending.get()
    if pending is None:
        raise RuntimeError("retry_context is not active")
    return pending


def notify_provider_retry(info: RetryInfo) -> None:
    pending = _pending.get()
    if pending is None:
        return
    pending.append(
        LLMResponse(
            content="",
            model="system",
            event_type="retrying",
            metadata={
                "retry_attempt": info.attempt,
                "retry_max": info.max_attempts,
                "reason": info.reason,
                "error": info.error[:200],
            },
        )
    )


def take_pending_retries() -> list[LLMResponse]:
    pending = _pending.get()
    if not pending:
        return []
    out = list(pending)
    pending.clear()
    return out


@contextmanager
def retry_context() -> Generator[None, None, None]:
    token = _pending.set([])
    try:
        yield
    finally:
        _pending.reset(token)
