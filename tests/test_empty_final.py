"""Empty final answer guard tests."""

from pathlib import Path

import pytest
from likecodex_engine.agent.guards import (
    empty_final_notice,
    empty_final_retry_message,
    has_visible_final_answer,
)
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_has_visible_final_answer() -> None:
    assert not has_visible_final_answer("")
    assert not has_visible_final_answer("   \n")
    assert has_visible_final_answer("done")


def test_empty_final_notice_and_retry_message() -> None:
    notice = empty_final_notice("mock", finish_reason="stop", reasoning_len=0)
    assert "empty final answer blocked" in notice
    assert "mock" in notice
    assert "Continue the same task" in empty_final_retry_message()


@pytest.mark.asyncio
async def test_empty_final_retries_then_succeeds(tmp_path: Path) -> None:
    tools = ToolRegistry(str(tmp_path))
    context = ContextManager()
    llm = MockProvider(
        responses=[
            LLMResponse(content=""),
            LLMResponse(content=""),
            LLMResponse(content="Here is the answer."),
        ]
    )
    loop = AgentLoop(
        llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )
    notices: list[str] = []
    finals: list[str] = []
    async for resp in loop.run("explain something"):
        if resp.event_type == "notice":
            notices.append(resp.content or "")
        if resp.event_type == "assistant" and resp.content:
            finals.append(resp.content)
    assert len(notices) == 2
    assert all("empty final answer blocked" in n for n in notices)
    assert finals == ["Here is the answer."]


@pytest.mark.asyncio
async def test_empty_final_stops_after_max_blocks(tmp_path: Path) -> None:
    tools = ToolRegistry(str(tmp_path))
    context = ContextManager()
    llm = MockProvider(
        responses=[
            LLMResponse(content=""),
            LLMResponse(content=""),
            LLMResponse(content=""),
        ]
    )
    loop = AgentLoop(
        llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )
    errors: list[str] = []
    async for resp in loop.run("explain something"):
        if resp.event_type == "error":
            errors.append(resp.content or "")
    assert len(errors) == 1
    assert "visible final answer" in errors[0]
