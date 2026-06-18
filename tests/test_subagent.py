"""Sub-agent orchestrator tests."""

import pytest
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.subagent import SubAgentOrchestrator
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_subagent_parallel(tmp_path):
    def factory():
        return AgentLoop(
            MockProvider(responses=[LLMResponse(content="ok")]),
            ToolRegistry(str(tmp_path)),
            ContextManager(system_prompt="test"),
        )

    orchestrator = SubAgentOrchestrator(factory)
    results = await orchestrator.run_parallel([("a", "task a"), ("b", "task b")])
    assert len(results) == 2
    assert all(r.success for r in results)
