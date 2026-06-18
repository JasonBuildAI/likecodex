"""Permission flow tests."""

from __future__ import annotations

import asyncio

import pytest
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, Role, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


class PromptThenDoneProvider(MockProvider):
    def __init__(self) -> None:
        super().__init__()

    async def complete(self, messages, tools=None, temperature=0.0, max_tokens=4096):
        if any(m.role == Role.TOOL for m in messages):
            return LLMResponse(content="done", model="mock")
        return LLMResponse(
            content="",
            tool_calls=[ToolCall(id="1", name="write_file", arguments={"path": "a.txt", "content": "hi"})],
            model="mock",
        )


@pytest.mark.asyncio
async def test_prompt_mode_waits_for_permission(tmp_path):
    tools = ToolRegistry(str(tmp_path))
    loop = AgentLoop(
        PromptThenDoneProvider(),
        tools,
        ContextManager(system_prompt="test"),
        permission_evaluator=PermissionEvaluator(ApprovalMode.AUTO),
    )

    outputs = []

    async def collect():
        async for resp in loop.run("write file"):
            outputs.append(resp)

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.1)
    pending = loop.list_pending_permissions()
    assert pending
    assert await loop.respond_permission(pending[0]["request_id"], True)
    await asyncio.wait_for(task, timeout=5)
    assert any(o.event_type == "tool_result" for o in outputs)
