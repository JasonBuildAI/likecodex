"""Subagent transcript replay with tool pairing sanitize."""

from __future__ import annotations

import json

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.subagent_store import SubagentSpec, SubagentStore
from likecodex_engine.agent.task import TaskTool
from likecodex_engine.context.manager import ContextManager, stable_tool_calls_json
from likecodex_engine.llm.base import LLMResponse, Message, Role
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.llm.tool_repair import INTERRUPTED_TOOL_RESULT
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_continue_replays_sanitized_dangling_tool_call(tmp_path) -> None:
    store = SubagentStore(str(tmp_path))
    spec = SubagentSpec(name="review", parent_session="sess-1", workspace_root=str(tmp_path))
    run = store.prepare_fresh(spec)
    calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "echo", "arguments": '{"text":"hi"}'},
        }
    ]
    messages = [
        Message(role=Role.USER, content="inspect"),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=calls,
            raw_tool_calls=stable_tool_calls_json(calls),
        ),
    ]
    store.save_completed(run, messages)

    captured: list[list[Message]] = []

    def factory(tool_whitelist, max_steps):
        loop = AgentLoop(
            MockProvider(responses=[LLMResponse(content="continued")]),
            ToolRegistry(str(tmp_path), register_defaults=False),
            ContextManager(system_prompt="sub"),
            permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
            is_subagent=True,
        )
        original = loop.context.get_messages

        def wrapped() -> list[Message]:
            msgs = original()
            captured.append(msgs)
            return msgs

        loop.context.get_messages = wrapped  # type: ignore[method-assign]
        return loop

    tool = TaskTool(factory, store=store, parent_session="sess-1", working_dir=str(tmp_path))
    out = json.loads(await tool.task("continue review", description="review", continue_from=run.ref))
    assert "result" in out
    assert captured, "expected subagent to request LLM messages"
    tool_msgs = [m for m in captured[0] if m.role == Role.TOOL]
    assert len(tool_msgs) == 1
    assert INTERRUPTED_TOOL_RESULT in tool_msgs[0].content


@pytest.mark.asyncio
async def test_subagent_store_roundtrip_preserves_tool_pairing(tmp_path) -> None:
    store = SubagentStore(str(tmp_path))
    spec = SubagentSpec(name="review", parent_session="sess-1", workspace_root=str(tmp_path))
    run = store.prepare_fresh(spec)
    calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "echo", "arguments": '{"text":"alpha"}'},
        }
    ]
    messages = [
        Message(role=Role.USER, content="go"),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=calls,
            raw_tool_calls=stable_tool_calls_json(calls),
        ),
        Message(role=Role.TOOL, content='{"text":"alpha"}', tool_call_id="c1"),
    ]
    store.save_completed(run, messages)
    continued = store.prepare_continue(run.ref, spec)
    ctx = ContextManager()
    ctx._log = list(continued.messages)
    replay = ctx.build_for_llm()
    tool_msgs = [m for m in replay if m.role == Role.TOOL]
    assert len(tool_msgs) == 1
    assert "alpha" in tool_msgs[0].content
