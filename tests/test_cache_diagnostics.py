"""Cache prefix diagnostics and per-turn usage events."""

from __future__ import annotations

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.context.cache_shape import (
    capture_prefix_shape,
    compare_prefix_shape,
    format_usage_line,
)
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


def test_capture_shape_normalizes_tool_order() -> None:
    schemas_a = [
        {"type": "function", "function": {"name": "b", "parameters": {}}},
        {"type": "function", "function": {"name": "a", "parameters": {}}},
    ]
    schemas_b = list(reversed(schemas_a))
    first = capture_prefix_shape("system", schemas_a, 0)
    second = capture_prefix_shape("system", schemas_b, 0)
    assert first.tools_hash == second.tools_hash
    assert first.prefix_hash == second.prefix_hash


def test_compare_shape_reports_tool_change() -> None:
    before = capture_prefix_shape("system", [], 0)
    after = capture_prefix_shape(
        "system",
        [{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
        0,
    )
    usage = {"prompt_cache_hit_tokens": 80, "prompt_cache_miss_tokens": 20}
    diag = compare_prefix_shape(before, after, usage)
    assert diag.prefix_changed
    assert "tools" in diag.prefix_change_reasons
    assert diag.cache_hit_tokens == 80
    assert diag.cache_miss_tokens == 20


def test_format_usage_line_includes_prefix_churn() -> None:
    usage = {
        "total_tokens": 110,
        "prompt_tokens": 100,
        "completion_tokens": 10,
        "prompt_cache_hit_tokens": 80,
        "prompt_cache_miss_tokens": 20,
    }
    from likecodex_engine.context.cache_shape import CacheDiagnostics

    diag = CacheDiagnostics(prefix_changed=True, prefix_change_reasons=["tools"])
    line = format_usage_line(usage, diag)
    assert "110 tok" in line
    assert "80 cached / 20 new" in line
    assert "cache prefix changed: tools" in line


def test_compare_shape_reports_log_rewrite() -> None:
    before = capture_prefix_shape("system", [], 0)
    after = capture_prefix_shape("system", [], 1)
    diag = compare_prefix_shape(before, after, None)
    assert diag.prefix_changed
    assert "log_rewrite" in diag.prefix_change_reasons


@pytest.mark.asyncio
async def test_loop_emits_usage_with_diagnostics(tmp_path) -> None:
    tools = ToolRegistry(working_dir=str(tmp_path))
    context = CacheFirstContext()
    llm = MockProvider(
        responses=[
            LLMResponse(
                content="done",
                usage={
                    "total_tokens": 120,
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 100,
                },
            )
        ]
    )
    loop = AgentLoop(
        llm=llm,
        tools=tools,
        context=context,
        permission_evaluator=PermissionEvaluator(),
        max_iterations=1,
    )
    events = [event async for event in loop.run("hello")]
    usage_events = [e for e in events if e.event_type == "usage"]
    assert len(usage_events) == 1
    assert usage_events[0].metadata["usage_source"] == "executor"
    assert usage_events[0].metadata["cache_diagnostics"]["prefix_changed"] is False
    assert "120 tok" in usage_events[0].content
