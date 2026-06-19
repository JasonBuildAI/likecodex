"""Stream recovery and early tool dispatch tests."""

from __future__ import annotations

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_recovers_interrupted_stream_after_partial_text(tmp_path) -> None:
    llm = MockProvider(
        stream_turns=[
            ["partial ", "__interrupt__"],
            ["continued"],
        ]
    )
    tools = ToolRegistry(str(tmp_path), register_defaults=False)
    loop = AgentLoop(
        llm,
        tools,
        ContextManager(),
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    outputs: list[LLMResponse] = []
    async for resp in loop.run("go"):
        outputs.append(resp)

    assert len(llm.calls) == 2
    second = llm.calls[1]
    assert second[-2].role.value == "assistant"
    assert second[-2].content == "partial "
    assert "Do not repeat" in second[-1].content

    deltas = [o.content for o in outputs if o.event_type == "delta"]
    assert "".join(deltas) == "partial continued"
    assistant_text = "".join(o.content or "" for o in outputs if o.event_type == "assistant")
    assert "continued" in assistant_text
    retries = [o for o in outputs if o.event_type == "retrying"]
    assert len(retries) == 1
    assert retries[0].metadata["retry_attempt"] == 1


@pytest.mark.asyncio
async def test_recovers_interrupted_partial_tool_without_executing(tmp_path) -> None:
    llm = MockProvider(
        stream_turns=[
            [("tool_start", "read_file"), "__interrupt__"],
            ["recovered"],
        ]
    )
    tools = ToolRegistry(str(tmp_path), register_defaults=False)
    tools.register(
        "read_file",
        {"description": "read", "parameters": {"type": "object", "properties": {}}},
        lambda **_: "{}",
    )
    loop = AgentLoop(
        llm,
        tools,
        ContextManager(),
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    async for _ in loop.run("go"):
        pass

    for msg in loop.context.messages:
        assert msg.role.value != "tool"

    second = llm.calls[1]
    assert "fresh complete tool call" in second[-1].content


@pytest.mark.asyncio
async def test_emits_tool_dispatch_during_stream(tmp_path) -> None:
    llm = MockProvider(
        stream_turns=[
            [
                ("tool_start", "read_file"),
                ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"}),
            ],
            ["done"],
        ]
    )
    tools = ToolRegistry(str(tmp_path), register_defaults=False)
    async def read_file(**_) -> str:
        return '{"content":"hi"}'

    tools.register(
        "read_file",
        {"description": "read", "parameters": {"type": "object", "properties": {}}},
        read_file,
    )
    loop = AgentLoop(
        llm,
        tools,
        ContextManager(),
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    dispatches = []
    async for resp in loop.run("go"):
        if resp.event_type == "tool_dispatch":
            dispatches.append(resp)

    assert len(dispatches) == 2
    assert dispatches[0].metadata["tool_name"] == "read_file"
    assert dispatches[0].metadata["partial"] is True
    assert dispatches[1].metadata["partial"] is False
    assert dispatches[1].metadata["arguments"] == {"path": "a.txt"}
