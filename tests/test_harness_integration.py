"""Harness integration tests for loop guards and output limits."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.output_limit import limit_tool_output
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_output_limit_caps_at_32kb():
    huge = "x" * 40000
    capped, notice = limit_tool_output(huge)
    assert len(capped.encode("utf-8")) <= 33000
    assert notice


@pytest.mark.asyncio
async def test_final_readiness_blocks_premature_done(tmp_path: Path) -> None:
    tools = ToolRegistry(str(tmp_path))
    tools.todo._todos = [{"id": "1", "content": "Finish work", "status": "in_progress"}]
    context = ContextManager()
    llm = MockProvider(
        responses=[
            LLMResponse(content="All done."),
            LLMResponse(content="Stopped after readiness notice."),
        ]
    )
    loop = AgentLoop(
        llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )
    outputs = []
    async for resp in loop.run("finish the task"):
        outputs.append(resp)
    assert any("final-readiness" in (o.content or "") for o in outputs)
    assert len(outputs) >= 2


@pytest.mark.asyncio
async def test_todo_write_requires_complete_step(tmp_path: Path) -> None:
    tools = ToolRegistry(str(tmp_path))
    tools.todo._todos = [{"id": "1", "content": "Ship", "status": "in_progress"}]
    context = ContextManager()
    llm = MockProvider(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="todo_write",
                        arguments={
                            "todos": [{"id": "1", "content": "Ship", "status": "completed"}],
                        },
                    )
                ],
            ),
            LLMResponse(content="Will sign off properly."),
        ]
    )
    loop = AgentLoop(
        llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )
    outputs = []
    async for resp in loop.run("mark todo done"):
        outputs.append(resp)
    tool_results = [o for o in outputs if o.event_type == "tool_result"]
    assert any("complete_step" in (o.content or "") for o in tool_results)
