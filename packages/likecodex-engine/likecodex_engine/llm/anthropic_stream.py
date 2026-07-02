"""Anthropic Claude streaming helpers with reconnection support."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.errors import StreamInterruptedError
from likecodex_engine.llm.openai_stream import is_conn_reset
from likecodex_engine.llm.retry import RetryInfo, notify_provider_retry

MAX_STREAM_RECONNECTS = 3


async def stream_anthropic_chat(
    stream: Any,
    *,
    model: str,
    parse_usage: Callable[[Any], dict[str, int]] | None = None,
) -> AsyncIterator[LLMResponse]:
    """Aggregate Anthropic stream events into unified delta/tool_dispatch/assistant events.

    Anthropic stream event types:
      - message_start: start of a message (contains usage)
      - content_block_start: start of a content block (text or tool_use)
      - content_block_delta: delta within a content block (text or input_json)
      - content_block_stop: end of a content block
      - message_delta: end of message (contains stop_reason and usage)
      - message_stop: final stop event
    """
    content_parts: list[str] = []
    pending_tool: dict[str, Any] | None = None
    tool_args_parts: list[str] = []
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    emitted = False
    current_block_index: int | None = None

    try:
        async for event in stream:
            event_type = getattr(event, "type", "")

            if event_type == "message_start":
                message = getattr(event, "message", None)
                if message and parse_usage:
                    usage = parse_usage(message)

            elif event_type == "content_block_start":
                block = getattr(event, "content_block", None)
                index = getattr(event, "index", None)
                if block is None:
                    continue
                current_block_index = index
                block_type = getattr(block, "type", "")
                if block_type == "text":
                    text = getattr(block, "text", "")
                    if text:
                        emitted = True
                        content_parts.append(text)
                        yield LLMResponse(
                            content=text,
                            model=model,
                            event_type="delta",
                        )
                elif block_type == "tool_use":
                    pending_tool = {
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "arguments": {},
                    }
                    tool_args_parts = []
                    emitted = True
                    yield LLMResponse(
                        content="",
                        model=model,
                        event_type="tool_dispatch",
                        metadata={
                            "tool_name": getattr(block, "name", ""),
                            "partial": True,
                        },
                    )

            elif event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta is None:
                    continue
                delta_type = getattr(delta, "type", "")
                if delta_type == "text_delta":
                    text = getattr(delta, "text", "")
                    if text:
                        emitted = True
                        content_parts.append(text)
                        yield LLMResponse(
                            content=text,
                            model=model,
                            event_type="delta",
                        )
                elif delta_type == "input_json_delta":
                    partial = getattr(delta, "partial_json", "")
                    if partial:
                        tool_args_parts.append(partial)

            elif event_type == "content_block_stop":
                if pending_tool is not None:
                    import json

                    raw = "".join(tool_args_parts)
                    try:
                        pending_tool["arguments"] = json.loads(raw) if raw else {}
                    except json.JSONDecodeError:
                        pending_tool["arguments"] = {}
                pending_tool = None
                tool_args_parts = []

            elif event_type == "message_delta":
                delta = getattr(event, "delta", None)
                if delta:
                    stop_reason = getattr(delta, "stop_reason", None)
                    if stop_reason:
                        finish_reason = stop_reason
                # Final usage in message_delta
                if parse_usage:
                    usage_delta = getattr(event, "usage", None)
                    if usage_delta:
                        usage = parse_usage(event)

    except Exception as exc:
        if emitted:
            raise StreamInterruptedError(str(exc)) from exc
        raise

    final_content = "".join(content_parts)
    if final_content or finish_reason:
        merged_usage = dict(usage or {})
        if finish_reason:
            merged_usage["finish_reason"] = finish_reason
        yield LLMResponse(
            content=final_content,
            model=model,
            usage=merged_usage or None,
            event_type="assistant",
        )


async def stream_anthropic_with_reconnect(
    create_stream: Callable[[], Awaitable[Any]],
    *,
    model: str,
    parse_usage: Callable[[Any], dict[str, int]] | None = None,
) -> AsyncIterator[LLMResponse]:
    """Replay the Anthropic stream request when the connection drops before any output."""
    last_error: Exception | None = None
    for attempt in range(MAX_STREAM_RECONNECTS + 1):
        try:
            stream = await create_stream()
            async for event in stream_anthropic_chat(
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
