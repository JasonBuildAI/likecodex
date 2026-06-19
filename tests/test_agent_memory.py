"""Agent memory tool tests."""

import json

import pytest
from likecodex_engine.tools.agent_memory import AgentMemoryTools


@pytest.mark.asyncio
async def test_remember_and_search(tmp_path):
    tools = AgentMemoryTools(str(tmp_path))
    await tools.remember("api-base", "Use https://api.example.com")
    out = json.loads(await tools.memory_search("api"))
    assert len(out["hits"]) == 1


@pytest.mark.asyncio
async def test_forget_archives(tmp_path):
    tools = AgentMemoryTools(str(tmp_path))
    await tools.remember("old-fact", "deprecated")
    out = json.loads(await tools.forget("old-fact"))
    assert out["forgotten"] is True
