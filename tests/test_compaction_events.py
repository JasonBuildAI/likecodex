"""Compaction SSE event tests."""

from __future__ import annotations

import pytest

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_loop_emits_compaction_started_and_done(tmp_path) -> None:
    ctx = CacheFirstContext(system_prompt="sys")
    ctx.set_working_dir(str(tmp_path))
    ctx.set_compact_llm(MockProvider(responses=[LLMResponse(content="summary")]))
    for i in range(4):
        ctx.add_user_message(f"user {i}")
        ctx.add_assistant_message(content=f"assistant {i}")
    ctx.last_prompt_tokens = int(ctx.compactor.context_window * 0.9)

    loop = AgentLoop(
        MockProvider(responses=[LLMResponse(content="done")]),
        ToolRegistry(str(tmp_path)),
        ctx,
        permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
    )

    events: list[str] = []
    async for resp in loop.run("finish"):
        events.append(resp.event_type)

    assert "compaction_started" in events
    assert "compaction_done" in events
    assert events.index("compaction_started") < events.index("compaction_done")
