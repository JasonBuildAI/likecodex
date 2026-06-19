"""Compaction loop tests."""

import pytest
from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.context.compaction import CacheFirstCompactor
from likecodex_engine.llm.base import LLMResponse, Message, Role
from likecodex_engine.llm.mock import MockProvider


class _CaptureProvider(MockProvider):
    last_user: str = ""

    async def complete(self, messages, tools=None, **kwargs):
        for m in messages:
            if m.role.value == "user":
                _CaptureProvider.last_user = m.content
        return await super().complete(messages, tools=tools, **kwargs)


@pytest.mark.asyncio
async def test_llm_compact_archives_and_resets(tmp_path):
    ctx = CacheFirstContext(system_prompt="sys")
    ctx.set_working_dir(str(tmp_path))
    ctx.set_compact_llm(MockProvider(responses=[LLMResponse(content="## Goal\nDone\n## Next step\nContinue")]))
    for i in range(5):
        ctx.add_user_message(f"user {i}")
        ctx.add_assistant_message(content=f"assistant {i}")
    ctx.last_prompt_tokens = int(ctx.compactor.context_window * 0.9)
    info = await ctx.compact_async()
    assert info["compacted"] is True
    assert ctx.cache_reset_count == 1
    assert any(SUMMARY_TAG in m.content for m in ctx._log for SUMMARY_TAG in ("<compaction-summary>", "summarized"))


@pytest.mark.asyncio
async def test_compact_async_passes_focus_instructions(tmp_path):
    ctx = CacheFirstContext(system_prompt="sys")
    ctx.set_working_dir(str(tmp_path))
    llm = _CaptureProvider(responses=[LLMResponse(content="## Goal\nDone")])
    ctx.set_compact_llm(llm)
    for i in range(3):
        ctx.add_user_message(f"user {i}")
        ctx.add_assistant_message(content=f"assistant {i}")
    await ctx.compact_async(instructions="preserve auth flow", force=True)
    assert "preserve auth flow" in _CaptureProvider.last_user


def test_compactor_split_pins_user():
    comp = CacheFirstCompactor()
    log = [
        Message(role=Role.USER, content="short goal"),
        Message(role=Role.ASSISTANT, content="did work"),
        Message(role=Role.TOOL, content="result"),
    ]
    pinned, foldable = comp.split_compactable(log)
    assert len(pinned) >= 1
    assert len(foldable) >= 2
