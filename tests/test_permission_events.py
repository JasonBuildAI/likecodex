"""Permission prompt/respond streaming tests."""

from __future__ import annotations

import asyncio
import json

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.llm.base import LLMResponse, Message, Role, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.permissions.policy import Decision, Policy, Rule
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_permission_prompt_and_respond(tmp_path) -> None:
    policy = Policy(mode=Decision.ASK, ask=[Rule.parse("Edit(**)")])
    evaluator = PermissionEvaluator(ApprovalMode.AUTO, policy, str(tmp_path))
    tools = ToolRegistry(str(tmp_path))
    llm = MockProvider(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="write_file", arguments={"path": "a.txt", "content": "hi"})
                ],
            ),
            LLMResponse(content="done"),
        ]
    )
    loop = AgentLoop(
        llm=llm,
        tools=tools,
        context=CacheFirstContext(),
        permission_evaluator=evaluator,
    )

    async def collect() -> list[LLMResponse]:
        out: list[LLMResponse] = []
        task = asyncio.create_task(_drain_loop(loop, out))
        await asyncio.sleep(0.05)
        pending = loop.list_pending_permissions()
        assert len(pending) == 1
        request_id = pending[0]["request_id"]
        assert await loop.respond_permission(request_id, True)
        await task
        return out

    events = await collect()
    permission_events = [e for e in events if e.event_type == "permission"]
    assert len(permission_events) == 1
    payload = json.loads(permission_events[0].content)
    assert payload["tool"] == "write_file"
    assert payload["request_id"]
    tool_results = [e for e in events if e.event_type == "tool_result"]
    assert tool_results
    assert "error" not in tool_results[-1].content.lower()


async def _drain_loop(loop: AgentLoop, out: list[LLMResponse]) -> None:
    async for event in loop.run("write a file"):
        out.append(event)
