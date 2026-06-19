"""Tests for OpenAI-compatible streaming aggregation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from likecodex_engine.llm.errors import StreamInterruptedError
from likecodex_engine.llm.openai_stream import (
    complete_with_reconnect,
    stream_openai_chat,
    stream_openai_chat_with_reconnect,
)


async def _chunks(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_stream_openai_chat_emits_delta_dispatch_and_final() -> None:
    chunks = _chunks(
        [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="hel", tool_calls=None))],
                model="mock",
                usage=None,
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content="lo",
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="c1",
                                    function=SimpleNamespace(name="read_file", arguments='{"path":'),
                                )
                            ],
                        )
                    )
                ],
                model="mock",
                usage=None,
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="c1",
                                    function=SimpleNamespace(name="read_file", arguments=' "a.txt"}'),
                                )
                            ],
                        )
                    )
                ],
                model="mock",
                usage=None,
            ),
        ]
    )

    events = [event async for event in stream_openai_chat(chunks, model="mock")]
    assert [event.event_type for event in events] == ["delta", "delta", "tool_dispatch", "assistant"]
    assert events[-1].content == "hello"
    assert events[-1].tool_calls[0].arguments == {"path": "a.txt"}


@pytest.mark.asyncio
async def test_stream_openai_chat_interrupt_after_partial_output() -> None:
    async def broken():
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="partial", tool_calls=None))],
            model="mock",
            usage=None,
        )
        raise ConnectionResetError("unexpected EOF")

    with pytest.raises(StreamInterruptedError):
        async for _ in stream_openai_chat(broken(), model="mock"):
            pass


@pytest.mark.asyncio
async def test_stream_reconnect_before_first_output() -> None:
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

    events = [
        event
        async for event in stream_openai_chat_with_reconnect(create_stream, model="mock")
    ]
    assert attempts["count"] == 2
    assert events[-1].content == "ok"


@pytest.mark.asyncio
async def test_complete_reconnect_before_response() -> None:
    attempts = {"count": 0}

    async def create_completion():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionResetError("connection reset by peer")
        return "ok"

    result = await complete_with_reconnect(create_completion)
    assert attempts["count"] == 2
    assert result == "ok"
