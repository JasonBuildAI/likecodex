"""Coordinator dual-model tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from likecodex_engine.agent.coordinator import (
    Coordinator,
    build_planner_readonly_tool_names,
    format_handoff,
    planner_tool_registry,
    should_plan,
)
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_should_plan_skips_greeting():
    assert not should_plan("hi")
    assert should_plan("refactor the auth module and add tests")


def test_planner_registry_excludes_write_tools(tmp_path):
    registry = ToolRegistry(str(tmp_path))
    names = planner_tool_registry(registry).list_tools()
    assert "read_file" in names
    assert "write_file" not in names
    assert "run_command" not in names


def test_format_handoff_includes_task_and_plan():
    text = format_handoff("fix bug", "1. read file\n2. patch")
    assert "fix bug" in text
    assert "1. read file" in text
    assert "executor" in text.lower()


@pytest.mark.asyncio
async def test_coordinator_runs_planner_then_executor(tmp_path: Path) -> None:
    tools = ToolRegistry(str(tmp_path))
    context = ContextManager()
    executor_llm = MockProvider(
        responses=[
            LLMResponse(content="Executed per plan."),
        ]
    )
    planner_llm = MockProvider(
        responses=[
            LLMResponse(content="Plan: edit main.py"),
        ]
    )
    executor = AgentLoop(
        executor_llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )
    coordinator = Coordinator(executor, planner_llm, planner_max_steps=5)
    events: list[str] = []
    async for resp in coordinator.run("implement feature"):
        events.append(resp.event_type or "")
    assert "phase" in events
    assert "plan" in events
    assert planner_llm.calls
    assert executor_llm.calls
    handoff_user = executor_llm.calls[0][-1].content
    assert "Plan: edit main.py" in handoff_user


@pytest.mark.asyncio
async def test_coordinator_planner_can_use_readonly_tools(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('x')\n", encoding="utf-8")
    tools = ToolRegistry(str(tmp_path))
    context = ContextManager()
    planner_llm = MockProvider(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="p1",
                        name="read_file",
                        arguments={"path": "main.py"},
                    )
                ],
            ),
            LLMResponse(content="Plan: keep main.py as-is"),
        ]
    )
    executor_llm = MockProvider(responses=[LLMResponse(content="done")])
    executor = AgentLoop(
        executor_llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )
    coordinator = Coordinator(executor, planner_llm, planner_max_steps=5)
    async for _ in coordinator.run("review main.py"):
        pass
    assert any("read_file" in str(call) for call in planner_llm.calls)


def test_build_planner_readonly_tool_names_includes_lsp():
    names = build_planner_readonly_tool_names(["read_file", "write_file", "lsp_hover"])
    assert "read_file" in names
    assert "lsp_hover" in names
    assert "write_file" not in names
