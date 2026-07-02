"""Streaming turn helpers for the agent loop."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import random
from typing import Any

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, ToolCall
from likecodex_engine.llm.errors import StreamInterruptedError
from likecodex_engine.llm.retry import take_pending_retries
from likecodex_engine.llm.tool_repair import merge_tool_calls

MAX_STREAM_RECOVERIES = 8

# Backoff schedule: 1s, 2s, 4s, 8s, 16s, 30s, 60s, 120s
_BACKOFF_SCHEDULE = [1, 2, 4, 8, 16, 30, 60, 120]


def backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter: 1s->2s->4s->8s->16s->30s->60s->120s + jitter.
    Uses a predefined schedule with random jitter of up to 50% of the delay.
    """
    idx = min(attempt - 1, len(_BACKOFF_SCHEDULE) - 1) if attempt > 0 else 0
    delay = _BACKOFF_SCHEDULE[idx]
    jitter = random.uniform(0, 0.5 * delay)
    return delay + jitter


def _build_response(
    content: str,
    tool_calls: list[ToolCall],
    llm: LLMProvider,
    usage: dict[str, Any] | None,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        model=getattr(llm, "model", ""),
        usage=usage,
    )


def stream_recovery_message(has_partial_text: bool, had_partial_tool: bool) -> str:
    if had_partial_tool:
        return (
            "The previous assistant response was interrupted while a tool call was streaming. "
            "Continue the same task now. If a tool is still needed, issue a fresh complete tool call "
            "from scratch; do not rely on any partial tool-call arguments from the interrupted stream."
        )
    if has_partial_text:
        return (
            "The previous assistant response was interrupted during streaming. Continue the same task "
            "from immediately after the partial assistant message above. Do not repeat text that is "
            "already visible."
        )
    return (
        "The previous assistant response was interrupted during streaming before visible answer text "
        "was completed. Continue the same task now and provide the next useful response."
    )


@dataclass
class StreamTurnResult:
    response: LLMResponse
    interrupted: bool = False
    partial_tool_started: bool = False
    partial_text: str = ""


async def stream_model_turn(
    llm: LLMProvider,
    messages: list[Message],
    tools: list[dict[str, Any]] | None,
) -> AsyncIterator[LLMResponse | StreamTurnResult]:
    """Stream one model turn, yielding deltas/dispatch events then a final result."""
    for retry in take_pending_retries():
        yield retry
    content_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    usage: dict[str, Any] | None = None
    partial_tool_started = False
    final_response: LLMResponse | None = None

    try:
        async for chunk in llm.stream(messages, tools=tools, temperature=0.0, max_tokens=4096):
            for retry in take_pending_retries():
                yield retry
            event_type = chunk.event_type or "assistant"
            if event_type == "delta" and chunk.content:
                content_parts.append(chunk.content)
                yield chunk
            elif event_type == "tool_dispatch":
                partial_tool_started = True
                yield chunk
            elif event_type == "stream_error":
                raise StreamInterruptedError(chunk.content or "stream interrupted")
            elif event_type == "assistant":
                final_response = chunk
                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)
                if chunk.content:
                    content_parts.append(chunk.content)
    except StreamInterruptedError:
        partial_text = "".join(content_parts)
        response = _build_response(partial_text, tool_calls, llm, usage)
        yield StreamTurnResult(
            response=merge_tool_calls(response),
            interrupted=True,
            partial_tool_started=partial_tool_started,
            partial_text=partial_text,
        )
        return

    for retry in take_pending_retries():
        yield retry

    if final_response is not None:
        merged = final_response.model_copy(
            update={
                "content": final_response.content or "".join(content_parts),
                "tool_calls": final_response.tool_calls or tool_calls,
            }
        )
        yield StreamTurnResult(
            response=merge_tool_calls(merged),
            partial_tool_started=partial_tool_started,
            partial_text=merged.content,
        )
        return

    response = _build_response("".join(content_parts), tool_calls, llm, usage)
    yield StreamTurnResult(
        response=merge_tool_calls(response),
        partial_tool_started=partial_tool_started,
        partial_text=response.content,
    )
