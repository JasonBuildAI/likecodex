"""Executor handoff guard tests."""

from pathlib import Path

import pytest
from likecodex_engine.agent.coordinator import EXECUTOR_HANDOFF_MARKER, format_handoff
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_handoff_guard_nudges_until_tool_use(tmp_path: Path) -> None:
    tools = ToolRegistry(str(tmp_path))
    context = ContextManager()
    llm = MockProvider(
        responses=[
            LLMResponse(content="I would edit the file."),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="read_file", arguments={"path": "main.py"}),
                ],
            ),
            LLMResponse(content="Read main.py and will edit next."),
        ]
    )
    loop = AgentLoop(
        llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
        executor_handoff_guard=True,
    )
    handoff = format_handoff("implement feature", "Plan: edit main.py")
    assert EXECUTOR_HANDOFF_MARKER in handoff
    notices = []
    async for resp in loop.run(handoff):
        if resp.event_type == "notice":
            notices.append(resp.content or "")
    assert any("executor-handoff" in n for n in notices)
