"""Tests for DeepSeek prefix-cache optimizations."""

from __future__ import annotations

import pytest
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager, stable_json_dumps, stable_tool_calls_json
from likecodex_engine.context.session_cache import SessionContextCache
from likecodex_engine.llm.cache_metrics import CacheMetrics
from likecodex_engine.llm.factory import create_provider
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_stable_json_is_deterministic() -> None:
    payload = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    assert stable_json_dumps(payload) == stable_json_dumps({"a": 1, "b": 2, "nested": {"y": 8, "z": 9}})


def test_tool_schema_sorted() -> None:
    registry = ToolRegistry()
    names = [item["function"]["name"] for item in registry.to_openai_schema()]
    assert names == sorted(names)


def test_context_block_uses_user_role() -> None:
    ctx = ContextManager()
    ctx.add_context_block("memory snippet")
    assert ctx.messages[-1].role.value == "user"
    assert ctx.messages[0].role.value == "system"
    assert ctx.messages[1].content.startswith("[Context]")


def test_single_system_message_after_context() -> None:
    ctx = ContextManager()
    ctx.add_context_block("block one")
    ctx.add_user_message("hello")
    system_count = sum(1 for m in ctx.messages if m.role.value == "system")
    assert system_count == 1


@pytest.mark.asyncio
async def test_cache_metrics_recorded_on_second_turn() -> None:
    metrics = CacheMetrics()
    tools = ToolRegistry()
    context = ContextManager()
    llm = MockProvider.for_cache_test()
    loop = AgentLoop(
        llm,
        tools,
        context,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    async for resp in loop.run("first prompt"):
        metrics.record(resp.usage)

    async for resp in loop.run("second prompt"):
        metrics.record(resp.usage)

    assert llm.calls[0][0].role.value == "system"
    assert metrics.total_hit_tokens > 0
    assert metrics.hit_rate > 0


@pytest.mark.asyncio
async def test_session_context_reuse() -> None:
    cache = SessionContextCache()
    ctx = ContextManager()
    ctx.add_user_message("prior turn")
    cache.put("sess-1", ctx)

    restored = cache.get("sess-1")
    assert restored is not None
    assert len(restored.messages) == 2
    assert restored.messages[1].content == "prior turn"


def test_create_provider_deepseek() -> None:
    provider = create_provider("deepseek", "deepseek-v4-flash", api_key="test-key")
    assert provider.model == "deepseek-v4-flash"


def test_assistant_tool_calls_stable_serialization() -> None:
    calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"path":"a.py"}'},
        }
    ]
    serialized = stable_tool_calls_json(calls)
    assert "call_1" in serialized
    ctx = ContextManager()
    ctx.add_assistant_message("", tool_calls=calls, raw_tool_calls=serialized)
    rebuilt = ctx.build_for_llm()
    assistant = next(m for m in reversed(rebuilt) if m.role.value == "assistant" and m.tool_calls)
    assert assistant.tool_calls == calls
