"""Provider retry notify tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from likecodex_engine.agent.streaming import stream_model_turn
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.llm.openai_stream import complete_with_reconnect, stream_openai_chat_with_reconnect
from likecodex_engine.llm.retry import RetryInfo, notify_provider_retry, retry_context, take_pending_retries


def test_notify_noop_without_retry_context() -> None:
    notify_provider_retry(RetryInfo(attempt=1, max_attempts=3, error="connection reset"))
    assert take_pending_retries() == []


@pytest.mark.asyncio
async def test_provider_retry_surfaces_through_stream_model_turn() -> None:
    llm = MockProvider(responses=[LLMResponse(content="done")])

    with retry_context():
        notify_provider_retry(RetryInfo(attempt=1, max_attempts=3, error="connection reset"))
        events = [event async for event in stream_model_turn(llm, [], None)]

    retries = [e for e in events if getattr(e, "event_type", "") == "retrying"]
    assert len(retries) == 1
    assert retries[0].metadata["reason"] == "provider"


@pytest.mark.asyncio
async def test_stream_reconnect_emits_provider_retry() -> None:
    attempts = {"count": 0}

    async def create_stream():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionResetError("connection reset by peer")

        async def ok():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="ok", tool_calls=None))],
                model="mock",
                usage=None,
            )

        return ok()

    with retry_context():
        async for _ in stream_openai_chat_with_reconnect(create_stream, model="mock"):
            pass
        retries = take_pending_retries()

    assert attempts["count"] == 2
    assert len(retries) == 1
    assert retries[0].metadata["reason"] == "provider"


@pytest.mark.asyncio
async def test_complete_reconnect_emits_provider_retry() -> None:
    attempts = {"count": 0}

    async def create_completion():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionResetError("connection reset by peer")
        return "ok"

    with retry_context():
        result = await complete_with_reconnect(create_completion)
        retries = take_pending_retries()

    assert result == "ok"
    assert attempts["count"] == 2
    assert len(retries) == 1
    assert retries[0].metadata["reason"] == "provider"
