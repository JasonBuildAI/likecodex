"""Task tool tests."""

import json

import pytest
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.task import TaskTool
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_task_tool_runs_subagent(tmp_path):
    parent = AgentLoop(
        MockProvider(responses=[LLMResponse(content="parent")]),
        ToolRegistry(str(tmp_path)),
        ContextManager(system_prompt="test"),
    )

    def factory(wl, ms):
        return AgentLoop(
            MockProvider(responses=[LLMResponse(content="sub result")]),
            ToolRegistry(str(tmp_path)),
            ContextManager(system_prompt="sub"),
            is_subagent=True,
        )

    parent.agent_factory = factory
    parent.tools.set_agent_factory(factory)
    task = TaskTool(factory)
    out = json.loads(await task.task("do something", description="demo"))
    assert "sub result" in out["result"]
