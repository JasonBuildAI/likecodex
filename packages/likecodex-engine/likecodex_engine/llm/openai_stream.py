"""Shared OpenAI-compatible streaming helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeVar

from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.errors import StreamInterruptedError
from likecodex_engine.llm.retry import RetryInfo, notify_provider_retry
from likecodex_engine.llm.tool_repair import repair_json

MAX_STREAM_RECONNECTS = 3

T = TypeVar("T")


def is_conn_reset(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "connection reset",
            "unexpected eof",
            "broken pipe",
            "incomplete chunked",
            "connection aborted",
        )
    )


async def stream_openai_chat(
    chunks: AsyncIterator[Any],
    *,
    model: str,
    parse_usage: Callable[[Any], dict[str, int]] | None = None,
) -> AsyncIterator[LLMResponse]:
    """Aggregate OpenAI-style stream chunks into delta/dispatch/assistant events."""
    content_parts: list[str] = []
    pending_tools: dict[int, dict[str, Any]] = {}
    dispatched: set[int] = set()
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    emitted = False

    try:
        async for chunk in chunks:
            if parse_usage is not None and getattr(chunk, "usage", None) is not None:
                usage = parse_usage(chunk.usage)
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta.content:
                emitted = True
                content_parts.append(delta.content)
                yield LLMResponse(
                    content=delta.content,
                    model=getattr(chunk, "model", None) or model,
                    event_type="delta",
                )
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if tc.index is not None else 0
                    slot = pending_tools.setdefault(
                        idx,
                        {"id": "", "name": "", "arguments": []},
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                        if idx not in dispatched:
                            dispatched.add(idx)
                            emitted = True
                            yield LLMResponse(
                                content="",
                                model=getattr(chunk, "model", None) or model,
                                event_type="tool_dispatch",
                                metadata={
                                    "tool_name": tc.function.name,
                                    "partial": True,
                                },
                            )
                    if tc.function and tc.function.arguments:
                        slot["arguments"].append(tc.function.arguments)
    except Exception as exc:
        if emitted:
            raise StreamInterruptedError(str(exc)) from exc
        raise

    tool_calls: list[ToolCall] = []
    for idx in sorted(pending_tools):
        slot = pending_tools[idx]
        args_text = "".join(slot["arguments"])
        parsed = repair_json(args_text) if args_text else {}
        tool_calls.append(
            ToolCall(
                id=slot["id"] or f"call_{idx}",
                name=slot["name"],
                arguments=parsed,
            )
        )

    final_content = "".join(content_parts)
    if final_content or tool_calls:
        merged_usage = dict(usage or {})
        if finish_reason:
            merged_usage["finish_reason"] = finish_reason
        yield LLMResponse(
            content=final_content,
            tool_calls=tool_calls,
            model=model,
            usage=merged_usage or None,
            event_type="assistant",
        )


async def stream_openai_chat_with_reconnect(
    create_stream: Callable[[], Awaitable[Any]],
    *,
    model: str,
    parse_usage: Callable[[Any], dict[str, int]] | None = None,
) -> AsyncIterator[LLMResponse]:
    """Replay the stream request when the connection drops before any output."""
    last_error: Exception | None = None
    for attempt in range(MAX_STREAM_RECONNECTS + 1):
        try:
            stream = await create_stream()
            async for event in stream_openai_chat(
                stream,
                model=model,
                parse_usage=parse_usage,
            ):
                yield event
            return
        except StreamInterruptedError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt >= MAX_STREAM_RECONNECTS or not is_conn_reset(exc):
                raise
            notify_provider_retry(
                RetryInfo(
                    attempt=attempt + 1,
                    max_attempts=MAX_STREAM_RECONNECTS,
                    error=str(exc),
                    reason="provider",
                )
            )
    if last_error is not None:
        raise last_error


async def complete_with_reconnect(
    create_completion: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = MAX_STREAM_RECONNECTS,
) -> T:
    """Replay a non-stream request when the connection drops before a response."""
    last_error: Exception | None = None
    for attempt in range(max_attempts + 1):
        try:
            return await create_completion()
        except StreamInterruptedError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts or not is_conn_reset(exc):
                raise
            notify_provider_retry(
                RetryInfo(
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    error=str(exc),
                    reason="provider",
                )
            )
    if last_error is not None:
        raise last_error
    raise RuntimeError("complete_with_reconnect exhausted without result")
