"""Tool dispatch event tests."""

from __future__ import annotations

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.llm.tool_repair import ensure_tool_call_ids
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_ensure_tool_call_ids_assigns_missing_ids() -> None:
    calls = ensure_tool_call_ids([ToolCall(id="", name="echo", arguments={"text": "x"})])
    assert calls[0].id.startswith("call_0_")


@pytest.mark.asyncio
async def test_loop_emits_full_tool_dispatch_before_execution(tmp_path) -> None:
    tools = ToolRegistry(str(tmp_path), register_defaults=False)

    async def echo(text: str = "", **_) -> str:
        return f'{{"text": "{text}"}}'

    tools.register(
        "echo",
        {
            "description": "echo",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
        },
        echo,
    )
    llm = MockProvider(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="", name="echo", arguments={"text": "hi"})],
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

    events: list[str] = []
    async for resp in loop.run("go"):
        events.append(resp.event_type)

    dispatch_idx = events.index("tool_dispatch")
    result_idx = events.index("tool_result")
    assert dispatch_idx < result_idx

    dispatches = [i for i, et in enumerate(events) if et == "tool_dispatch"]
    assert len(dispatches) >= 1
