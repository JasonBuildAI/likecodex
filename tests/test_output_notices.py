"""Tool output truncation and finish_reason notice tests."""

from __future__ import annotations

import pytest
from likecodex_engine.agent.guards import finish_reason_notice
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.output_limit import MAX_TOOL_OUTPUT_BYTES, limit_tool_output
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_limit_tool_output_preserves_short() -> None:
    body, notice = limit_tool_output("hello")
    assert body == "hello"
    assert notice == ""


def test_limit_tool_output_head_tail_and_notice() -> None:
    huge = "a" * 20000 + "MIDDLE" + "b" * 20000
    body, notice = limit_tool_output(huge)
    assert len(body.encode("utf-8")) <= MAX_TOOL_OUTPUT_BYTES + 200
    assert "MIDDLE" not in body
    assert "truncated" in body
    assert notice.startswith("tool output truncated:")
    assert "bytes elided" in notice


def test_limit_tool_output_utf8_safe() -> None:
    text = "你好" * 20000
    body, notice = limit_tool_output(text)
    assert notice
    body.encode("utf-8")  # must be valid UTF-8


def test_finish_reason_notice_mapping() -> None:
    assert finish_reason_notice({"finish_reason": "length"}) == "response truncated: hit max output tokens"
    assert finish_reason_notice({"finish_reason": "content_filter"}) == "response blocked by content filter"
    assert finish_reason_notice({"finish_reason": "repetition_truncation"}) == (
        "response truncated: model repetition detected"
    )
    assert finish_reason_notice({"finish_reason": "stop"}) is None
    assert finish_reason_notice(None) is None


@pytest.mark.asyncio
async def test_loop_emits_truncation_and_finish_notices(tmp_path) -> None:
    tools = ToolRegistry(str(tmp_path))

    async def huge_echo(**kwargs: object) -> str:
        return "x" * 40000

    tools.register(
        "huge_echo",
        {"description": "return huge output", "parameters": {"type": "object", "properties": {}}},
        huge_echo,
        read_only=True,
    )

    llm = MockProvider(
        responses=[
            LLMResponse(
                content="calling tool",
                tool_calls=[ToolCall(id="c1", name="huge_echo", arguments={})],
                usage={"finish_reason": "length"},
            ),
            LLMResponse(content="done"),
        ]
    )
    loop = AgentLoop(
        llm,
        tools,
        ContextManager(),
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    notices: list[str] = []
    async for event in loop.run("run huge echo"):
        if event.event_type == "notice":
            notices.append(event.content or "")

    assert any("response truncated: hit max output tokens" in n for n in notices)
    assert any(n.startswith("tool output truncated:") for n in notices)
