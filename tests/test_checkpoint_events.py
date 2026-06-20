"""Checkpoint SSE event tests."""

from __future__ import annotations

import json

import pytest
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_loop_emits_checkpoint_before_write_tool(tmp_path) -> None:
    target = tmp_path / "main.py"
    target.write_text("print(1)", encoding="utf-8")
    tools = ToolRegistry(str(tmp_path))
    loop = AgentLoop(
        MockProvider(
            responses=[
                LLMResponse(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="1",
                            name="write_file",
                            arguments={"path": "main.py", "content": "print(2)"},
                        )
                    ],
                ),
                LLMResponse(content="Updated main.py."),
            ]
        ),
        tools,
        ContextManager(),
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    checkpoints: list[dict] = []
    async for resp in loop.run("update main.py"):
        if resp.event_type == "checkpoint":
            checkpoints.append(json.loads(resp.content or "{}"))

    assert len(checkpoints) == 1
    assert checkpoints[0]["label"] == "write_file"
    assert checkpoints[0]["files"] == ["main.py"]
    assert checkpoints[0]["checkpoint_id"]
