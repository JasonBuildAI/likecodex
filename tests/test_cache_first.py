"""Tests for CacheFirstContext three-region model."""

from __future__ import annotations

from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.llm.base import Role


def test_prefix_hash_stable_when_log_grows() -> None:
    ctx = CacheFirstContext()
    h0 = ctx.prefix_hash()
    ctx.add_user_message("hello")
    ctx.add_assistant_message("hi")
    assert ctx.prefix_hash() == h0


def test_scratch_not_in_llm_payload() -> None:
    ctx = CacheFirstContext()
    ctx.add_scratch("planner scratch")
    ctx.add_user_message("task")
    payload = ctx.build_for_llm()
    assert all("planner scratch" not in m.content for m in payload)


def test_plan_block_is_user_message() -> None:
    ctx = CacheFirstContext()
    ctx.add_plan_block("step 1\nstep 2")
    assert ctx.messages[-1].role == Role.USER
    assert ctx.messages[-1].content.startswith("[Plan]")


def test_compaction_resets_log_preserves_prefix() -> None:
    ctx = CacheFirstContext(context_window=1000, compact_ratio=0.5)
    h0 = ctx.prefix_hash()
    ctx.add_user_message("a" * 500)
    ctx.add_assistant_message("b" * 500)
    ctx.record_prompt_tokens({"prompt_tokens": 600})
    assert ctx.cache_reset_count >= 1
    assert ctx.prefix_hash() == h0
    assert len(ctx._log) <= 2
