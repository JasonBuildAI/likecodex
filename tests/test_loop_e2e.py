"""Loop end-to-end tests aligned with Reasonix loop_e2e coverage."""

from __future__ import annotations

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse, ToolCall
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_well_formed_tool_loop_round_trips(tmp_path) -> None:
    tools = ToolRegistry(str(tmp_path), register_defaults=False)
    tools.register(
        "echo",
        {
            "description": "echo text",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
        },
        lambda text="", **_: f'{{"text": "{text}"}}',
    )
    llm = MockProvider(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "hi"})],
            ),
            LLMResponse(content="all set"),
        ]
    )
    loop = AgentLoop(
        llm,
        tools,
        ContextManager(),
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    async for _ in loop.run("go"):
        pass

    last = loop.context.messages[-1]
    assert last.role.value == "assistant"
    assert last.content == "all set"


@pytest.mark.asyncio
async def test_parallel_read_only_tools_execute(tmp_path) -> None:
    calls: list[str] = []

    async def read_file(path: str = "", **_) -> str:
        calls.append(path)
        return f'{{"path": "{path}"}}'

    tools = ToolRegistry(str(tmp_path), register_defaults=False)
    tools.register(
        "read_file",
        {
            "description": "read",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
        read_file,
    )
    llm = MockProvider(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(id="1", name="read_file", arguments={"path": "a.txt"}),
                    ToolCall(id="2", name="read_file", arguments={"path": "b.txt"}),
                ],
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

    async for _ in loop.run("go"):
        pass

    assert sorted(calls) == ["a.txt", "b.txt"]


@pytest.mark.asyncio
async def test_multi_tool_empty_ids_survive_pairing(tmp_path) -> None:
    tools = ToolRegistry(str(tmp_path), register_defaults=False)

    async def echo(text: str = "", **_) -> str:
        return f'{{"text": "{text}"}}'

    tools.register(
        "echo",
        {
            "description": "echo text",
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
                tool_calls=[
                    ToolCall(id="", name="echo", arguments={"text": "alpha"}),
                    ToolCall(id="", name="echo", arguments={"text": "beta"}),
                ],
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

    async for _ in loop.run("go"):
        pass

    tool_results = [m.content for m in loop.context.messages if m.role.value == "tool"]
    assert len(tool_results) == 2
    assert tool_results[0] != tool_results[1]
    assert "alpha" in tool_results[0]
    assert "beta" in tool_results[1]

    replay = loop.context.get_messages()
    replay_tools = [m for m in replay if m.role.value == "tool"]
    assert len(replay_tools) == 2
    assert replay_tools[0].content != replay_tools[1].content
