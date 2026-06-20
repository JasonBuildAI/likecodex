"""Parallel tasks tests."""

import json

import pytest
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.parallel_tasks import ParallelTasksTool
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.tools.registry import ToolRegistry


def _loop_factory(tmp_path):
    def factory(_wl, _ms):
        return AgentLoop(
            MockProvider(responses=[LLMResponse(content="ok")]),
            ToolRegistry(str(tmp_path)),
            ContextManager(system_prompt="t"),
        )

    return factory


def _done_loop_factory(tmp_path):
    def factory(_wl, _ms):
        return AgentLoop(
            MockProvider(responses=[LLMResponse(content="done")]),
            ToolRegistry(str(tmp_path)),
            ContextManager(system_prompt="t"),
        )

    return factory


@pytest.mark.asyncio
async def test_parallel_tasks_requires_two(tmp_path):
    tool = ParallelTasksTool(_loop_factory(tmp_path))
    out = json.loads(await tool.parallel_tasks([{"prompt": "one"}]))
    assert "error" in out


@pytest.mark.asyncio
async def test_parallel_tasks_runs_both(tmp_path):
    tool = ParallelTasksTool(_done_loop_factory(tmp_path))
    out = json.loads(
        await tool.parallel_tasks([{"prompt": "a", "description": "A"}, {"prompt": "b", "description": "B"}])
    )
    assert len(out["tasks"]) == 2
