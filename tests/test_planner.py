"""Planner tests."""

import pytest
from likecodex_engine.agent.planner import Planner
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.mock import MockProvider


@pytest.mark.asyncio
async def test_planner_fallback_on_bad_json():
    provider = MockProvider(responses=[LLMResponse(content="not-json")])
    planner = Planner(provider)
    plan = await planner.plan("1", "build feature")
    assert plan.reasoning
    assert isinstance(plan.steps, list)
