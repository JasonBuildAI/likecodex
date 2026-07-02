"""Tests for DeepSeek-specific tools and utilities.

Tests cover:
- deepseek_tools: reasoning helpers, cost estimate, prompt optimization
- smart_router: task classification, fallback routing, rule management
- cost_tracker: per-session tracking, cost calculation, persistence
- cache_metrics: hit rate calculation, recording
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from likecodex_engine.llm.cache_metrics import CacheMetrics, global_cache_metrics, reset_global_cache_metrics
from likecodex_engine.llm.smart_router import (
    SmartRouter,
    TaskType,
    ModelChoice,
    RouterRule,
    DEFAULT_RULES,
    get_router,
    reset_router,
)
from likecodex_engine.llm.cost_tracker import (
    CostTracker,
    TokenUsage,
    SessionCostRecord,
    get_cost_tracker,
    reset_cost_tracker,
)
from likecodex_engine.tools.deepseek_tools import (
    _build_reasoning_prompt,
    _extract_reasoning_steps,
    _extract_steps_from_answer,
    TOOL_DEFINITIONS,
)


# =========================================================================
# Cache Metrics Tests
# =========================================================================


class TestCacheMetrics:
    def test_empty_metrics(self) -> None:
        m = CacheMetrics()
        assert m.hit_rate == 0.0
        assert m.recent_hit_rate == 0.0
        assert m.request_count == 0

    def test_record_hit(self) -> None:
        m = CacheMetrics()
        m.record({"prompt_cache_hit_tokens": 100, "prompt_cache_miss_tokens": 0})
        assert m.request_count == 1
        assert m.total_hit_tokens == 100
        assert m.total_miss_tokens == 0
        assert m.hit_rate == 1.0

    def test_record_miss(self) -> None:
        m = CacheMetrics()
        m.record({"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 200})
        assert m.request_count == 1
        assert m.total_hit_tokens == 0
        assert m.total_miss_tokens == 200
        assert m.hit_rate == 0.0

    def test_record_mixed(self) -> None:
        m = CacheMetrics()
        m.record({"prompt_cache_hit_tokens": 300, "prompt_cache_miss_tokens": 700})
        assert m.hit_rate == 0.3
        assert m.recent_hit_rate == 0.3

    def test_record_none(self) -> None:
        m = CacheMetrics()
        m.record(None)
        assert m.request_count == 0

    def test_recent_hit_rate(self) -> None:
        m = CacheMetrics()
        for _ in range(10):
            m.record({"prompt_cache_hit_tokens": 80, "prompt_cache_miss_tokens": 20})
        assert m.recent_hit_rate == 0.8

    def test_reset(self) -> None:
        m = CacheMetrics()
        m.record({"prompt_cache_hit_tokens": 100, "prompt_cache_miss_tokens": 0})
        m.reset()
        assert m.request_count == 0
        assert m.hit_rate == 0.0

    def test_to_dict(self) -> None:
        m = CacheMetrics()
        m.record({"prompt_cache_hit_tokens": 100, "prompt_cache_miss_tokens": 900})
        d = m.to_dict()
        assert d["hit_rate"] == 0.1
        assert d["request_count"] == 1
        assert d["total_hit_tokens"] == 100

    def test_global_metrics_singleton(self) -> None:
        reset_global_cache_metrics()
        m1 = global_cache_metrics()
        m2 = global_cache_metrics()
        assert m1 is m2


# =========================================================================
# SmartRouter Tests
# =========================================================================


class TestSmartRouter:
    def test_singleton(self) -> None:
        reset_router()
        r1 = get_router()
        r2 = get_router()
        assert r1 is r2

    def test_classify_simple_qa(self) -> None:
        router = SmartRouter()
        rule = router.classify("What is the capital of France?")
        assert rule.task_type == TaskType.A_SIMPLE_QA
        assert rule.model == ModelChoice.FLASH

    def test_classify_code_task(self) -> None:
        router = SmartRouter()
        rule = router.classify("Implement a binary search tree in Python")
        assert rule.task_type == TaskType.B_CODE_TASK

    def test_classify_complex_reasoning(self) -> None:
        router = SmartRouter()
        rule = router.classify("Prove the Riemann hypothesis using complex analysis")
        assert rule.task_type == TaskType.C_COMPLEX_REASONING

    def test_classify_architecture(self) -> None:
        router = SmartRouter()
        rule = router.classify("Design a microservices architecture for an e-commerce platform")
        assert rule.task_type == TaskType.C_COMPLEX_REASONING

    def test_classify_debug(self) -> None:
        router = SmartRouter()
        rule = router.classify("Fix this race condition in the concurrent queue implementation")
        assert rule.task_type == TaskType.C_COMPLEX_REASONING

    def test_classify_creative(self) -> None:
        router = SmartRouter()
        rule = router.classify("Write a blog post about AI safety")
        assert rule.task_type == TaskType.D_CREATIVE_ANALYSIS

    def test_fallback_simple(self) -> None:
        router = SmartRouter()
        rule = router.classify("Hello world")
        assert rule.name == "fallback_simple"

    def test_fallback_code(self) -> None:
        router = SmartRouter()
        rule = router.classify("def calculate(x, y): return x + y")
        assert rule.task_type == TaskType.B_CODE_TASK

    def test_route_result_structure(self) -> None:
        router = SmartRouter()
        result = router.route("What is Python?")
        assert "task_type" in result
        assert "model" in result
        assert "rule_name" in result
        assert "query" in result

    def test_route_and_create_provider(self) -> None:
        router = SmartRouter()
        result = router.route_and_create_provider("Implement a sorting algorithm")
        assert "provider_kwargs" in result
        assert result["provider_kwargs"]["provider"] == "deepseek"

    def test_add_rule(self) -> None:
        router = SmartRouter()
        rule = RouterRule(
            name="custom_test",
            keywords=["custom_test_keyword"],
            task_type=TaskType.A_SIMPLE_QA,
            model=ModelChoice.FLASH,
            priority=100,
        )
        router.add_rule(rule)
        result = router.route("custom_test_keyword query")
        assert result["rule_name"] == "custom_test"

    def test_remove_rule(self) -> None:
        router = SmartRouter()
        assert router.remove_rule("nonexistent") is False
        assert router.remove_rule("simple_qa") is True

    def test_get_rules(self) -> None:
        router = SmartRouter()
        rules = router.get_rules()
        assert len(rules) == len(DEFAULT_RULES)
        assert all("name" in r for r in rules)
        assert all("priority" in r for r in rules)

    def test_custom_classifier(self) -> None:
        def classifier(query: str) -> TaskType | None:
            if query.startswith("CUSTOM"):
                return TaskType.C_COMPLEX_REASONING
            return None

        router = SmartRouter(custom_classifier=classifier)
        result = router.route("CUSTOM complex analysis")
        assert result["task_type"] == TaskType.C_COMPLEX_REASONING.value

    def test_metrics_tracking(self) -> None:
        router = SmartRouter()
        router.route("What is Go?")
        router.route("Implement a web server")
        router.route("Prove Fermat's theorem")
        metrics = router.get_metrics()
        assert metrics["total_routed"] == 3
        assert metrics["type_a_count"] >= 1
        assert metrics["type_b_count"] >= 1
        assert metrics["type_c_count"] >= 1

    def test_reset_metrics(self) -> None:
        router = SmartRouter()
        router.route("What is Python?")
        router.reset_metrics()
        metrics = router.get_metrics()
        assert metrics["total_routed"] == 0

    def test_route_priority(self) -> None:
        """Higher priority rules should match before lower ones."""
        router = SmartRouter()
        # "implement" should match code_generation (priority 20) before other rules
        result = router.route("Implement a solution")
        assert result["rule_name"] == "code_generation"


# =========================================================================
# Cost Tracker Tests
# =========================================================================


class TestTokenUsage:
    def test_default_values(self) -> None:
        u = TokenUsage()
        assert u.total_tokens == 0
        assert u.total_cost == 0.0
        assert u.cache_hit_rate == 0.0

    def test_from_dict(self) -> None:
        u = TokenUsage.from_dict({
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_cache_hit_tokens": 30,
            "prompt_cache_miss_tokens": 70,
            "model": "deepseek-v4-flash",
        })
        assert u.prompt_tokens == 100
        assert u.completion_tokens == 50
        assert u.cache_hit_tokens == 30
        assert u.cache_miss_tokens == 70
        assert u.total_tokens == 150

    def test_cost_calculation_flash(self) -> None:
        u = TokenUsage(prompt_tokens=1000, completion_tokens=500, model="deepseek-v4-flash")
        assert u.input_cost > 0
        assert u.output_cost > 0
        assert u.total_cost == round(u.input_cost + u.output_cost, 8)

    def test_cache_hit_rate(self) -> None:
        u = TokenUsage(cache_hit_tokens=800, cache_miss_tokens=200)
        assert u.cache_hit_rate == 0.8

    def test_to_dict(self) -> None:
        u = TokenUsage(prompt_tokens=100, completion_tokens=50, model="deepseek-v4-pro")
        d = u.to_dict()
        assert d["model"] == "deepseek-v4-pro"
        assert d["total_tokens"] == 150
        assert "total_cost" in d

    def test_pro_thinking_pricing(self) -> None:
        u = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            reasoning_tokens=200,
            model="deepseek-v4-pro-thinking",
        )
        assert u.total_cost > 0


class TestSessionCostRecord:
    def test_empty_record(self) -> None:
        r = SessionCostRecord(session_id="test-session")
        assert r.request_count == 0
        assert r.total_cost == 0.0
        assert r.total_tokens == 0

    def test_add_usage(self) -> None:
        r = SessionCostRecord(session_id="test-session")
        u = TokenUsage(prompt_tokens=100, completion_tokens=50, model="deepseek-v4-flash")
        r.add_usage(u)
        assert r.request_count == 1
        assert r.total_tokens == 150

    def test_multiple_usages(self) -> None:
        r = SessionCostRecord(session_id="test-session")
        r.add_usage(TokenUsage(prompt_tokens=100, completion_tokens=50))
        r.add_usage(TokenUsage(prompt_tokens=200, completion_tokens=100))
        assert r.request_count == 2
        assert r.total_tokens == 450

    def test_cache_hit_rate(self) -> None:
        r = SessionCostRecord(session_id="test-session")
        r.add_usage(TokenUsage(cache_hit_tokens=800, cache_miss_tokens=200))
        r.add_usage(TokenUsage(cache_hit_tokens=600, cache_miss_tokens=400))
        assert r.overall_cache_hit_rate == 0.7

    def test_to_dict(self) -> None:
        r = SessionCostRecord(session_id="s1")
        r.add_usage(TokenUsage(prompt_tokens=1000, completion_tokens=500, model="deepseek-v4-flash"))
        d = r.to_dict()
        assert d["session_id"] == "s1"
        assert d["request_count"] == 1
        assert "total_cost" in d
        assert "duration_seconds" in d

    def test_summary_dict(self) -> None:
        r = SessionCostRecord(session_id="s1")
        r.add_usage(TokenUsage(prompt_tokens=1000, completion_tokens=500))
        s = r.summary_dict()
        assert set(s.keys()) == {"session_id", "requests", "total_cost", "total_tokens", "cache_hit_rate"}


class TestCostTracker:
    def test_get_or_create_session(self) -> None:
        tracker = CostTracker()
        record = tracker.get_or_create_session("test")
        assert record.session_id == "test"
        # Same ID returns same record
        assert tracker.get_or_create_session("test") is record

    def test_record_usage(self) -> None:
        tracker = CostTracker()
        usage = tracker.record_usage("s1", TokenUsage(prompt_tokens=100, completion_tokens=50))
        assert isinstance(usage, TokenUsage)
        record = tracker.get_session_cost("s1")
        assert record is not None
        assert record.request_count == 1

    def test_record_usage_dict(self) -> None:
        tracker = CostTracker()
        tracker.record_usage("s1", {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "model": "deepseek-v4-flash",
        })
        record = tracker.get_session_cost("s1")
        assert record is not None
        assert record.request_count == 1

    def test_get_session_cost_nonexistent(self) -> None:
        tracker = CostTracker()
        assert tracker.get_session_cost("nonexistent") is None

    def test_record_switch_model(self) -> None:
        tracker = CostTracker()
        tracker.record_switch_model("s1")
        record = tracker.get_session_cost("s1")
        assert record is not None
        assert record.model_switch_count == 1

    def test_get_all_sessions(self) -> None:
        tracker = CostTracker()
        tracker.record_usage("s1", TokenUsage())
        tracker.record_usage("s2", TokenUsage())
        sessions = tracker.get_all_sessions()
        assert len(sessions) == 2

    def test_get_all_summaries(self) -> None:
        tracker = CostTracker()
        tracker.record_usage("s1", TokenUsage(prompt_tokens=100, completion_tokens=50))
        summaries = tracker.get_all_summaries()
        assert len(summaries) == 1
        assert "session_id" in summaries[0]

    def test_get_total_cost_empty(self) -> None:
        tracker = CostTracker()
        total = tracker.get_total_cost()
        assert total["total_sessions"] == 0
        assert total["total_cost"] == 0.0

    def test_get_total_cost_with_data(self) -> None:
        tracker = CostTracker()
        tracker.record_usage("s1", TokenUsage(prompt_tokens=1000, completion_tokens=500))
        total = tracker.get_total_cost()
        assert total["total_sessions"] == 1
        assert total["total_cost"] > 0

    def test_calculate_cost(self) -> None:
        tracker = CostTracker()
        cost = tracker.calculate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            cache_hit_tokens=800,
            cache_miss_tokens=200,
            model="deepseek-v4-flash",
        )
        assert "input_cost" in cost
        assert "output_cost" in cost
        assert "total_cost" in cost
        assert cost["cache_hit_rate"] == 0.8

    def test_clear_session(self) -> None:
        tracker = CostTracker()
        tracker.record_usage("s1", TokenUsage())
        assert tracker.clear_session("s1") is True
        assert tracker.clear_session("nonexistent") is False

    def test_reset_all(self) -> None:
        tracker = CostTracker()
        tracker.record_usage("s1", TokenUsage())
        tracker.reset_all()
        assert len(tracker.get_all_sessions()) == 0

    def test_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            persist_path = str(Path(tmpdir) / "cost.json")
            tracker = CostTracker(persist_path=persist_path)
            tracker.record_usage("s1", TokenUsage(prompt_tokens=100, completion_tokens=50))

            # Create a new tracker with same path - should load data
            tracker2 = CostTracker(persist_path=persist_path)
            record = tracker2.get_session_cost("s1")
            assert record is not None
            assert record.request_count == 1


# =========================================================================
# DeepSeek Tools Helper Tests
# =========================================================================


class TestDeepSeekToolsRegistry:
    def test_tools_registered(self) -> None:
        """Verify all expected tools are registered."""
        expected_tools = [
            "deepseek_cache_analyze",
            "deepseek_reasoning",
            "deepseek_switch_model",
            "deepseek_cost_estimate",
            "deepseek_tune_prompt",
        ]
        for name in expected_tools:
            assert name in TOOL_DEFINITIONS, f"Tool {name} not registered"

    def test_tool_has_handler(self) -> None:
        for name, definition in TOOL_DEFINITIONS.items():
            assert "handler" in definition
            assert callable(definition["handler"])

    def test_tool_has_description(self) -> None:
        for name, definition in TOOL_DEFINITIONS.items():
            assert definition.get("description"), f"Tool {name} missing description"

    def test_reasoning_tool_parameters(self) -> None:
        tool = TOOL_DEFINITIONS["deepseek_reasoning"]
        params = tool.get("parameters", {}).get("properties", {})
        assert "question" in params
        assert "reasoning_steps" in params
        assert "output_format" in params


class TestReasoningHelpers:
    def test_build_reasoning_prompt_structured(self) -> None:
        prompt = _build_reasoning_prompt(
            question="What is 2+2?",
            context="",
            detail_level="medium",
            reasoning_steps=3,
            output_format="structured",
        )
        assert "Step 1:" in prompt
        assert "Step 2:" in prompt
        assert "Step 3:" in prompt
        assert "What is 2+2?" in prompt

    def test_build_reasoning_prompt_with_context(self) -> None:
        prompt = _build_reasoning_prompt(
            question="Solve this problem",
            context="We are in math class",
            detail_level="high",
            reasoning_steps=4,
            output_format="structured",
        )
        assert "We are in math class" in prompt

    def test_build_reasoning_prompt_freeform(self) -> None:
        prompt = _build_reasoning_prompt(
            question="Hello?",
            context="",
            detail_level="low",
            reasoning_steps=2,
            output_format="freeform",
        )
        assert "Step 1:" not in prompt

    def test_extract_reasoning_steps(self) -> None:
        content = """Step 1: Analyze the problem
This is step 1 content.

Step 2: Consider solutions
This is step 2 content with more detail."""
        steps = _extract_reasoning_steps(content)
        assert len(steps) == 2
        assert "Analyze" in steps[0]["title"]
        assert "step 1" in steps[0]["content"].lower()

    def test_extract_reasoning_steps_bold_format(self) -> None:
        content = """**Step 1: Analysis**
First step details.

**Step 2: Solution**
Second step details."""
        steps = _extract_reasoning_steps(content)
        assert len(steps) == 2
        assert "Analysis" in steps[0]["title"]

    def test_extract_reasoning_steps_empty(self) -> None:
        steps = _extract_reasoning_steps("")
        assert steps == []

    def test_extract_steps_from_answer_markdown(self) -> None:
        answer = """**Step 1: Understand**
Read the question carefully.

**Step 2: Solve**
Apply the formula.

**Conclusion**
Final answer: 42."""
        steps = _extract_steps_from_answer(answer)
        assert len(steps) >= 2

    def test_extract_steps_from_answer_numbered(self) -> None:
        answer = """1. First step
First step content.

2. Second step
Second step content."""
        steps = _extract_steps_from_answer(answer)
        assert len(steps) >= 2

    def test_extract_steps_from_answer_empty(self) -> None:
        steps = _extract_steps_from_answer("")
        assert steps == []


# =========================================================================
# Edge Cases
# =========================================================================


class TestEdgeCases:
    def test_smart_router_empty_query(self) -> None:
        router = SmartRouter()
        result = router.route("")
        assert result is not None
        assert "model" in result

    def test_smart_router_very_long_query(self) -> None:
        router = SmartRouter()
        query = "a " * 1000
        result = router.route(query)
        assert result["task_type"] == TaskType.C_COMPLEX_REASONING.value

    def test_cost_tracker_negative_tokens(self) -> None:
        u = TokenUsage(prompt_tokens=-1, completion_tokens=0)
        assert u.total_tokens == -1  # System allows but cost should handle gracefully

    def test_cache_metrics_zero_division(self) -> None:
        m = CacheMetrics()
        m.record({"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0})
        assert m.hit_rate == 0.0

    def test_session_cost_record_multiple_models(self) -> None:
        r = SessionCostRecord(session_id="multi-model")
        r.add_usage(TokenUsage(prompt_tokens=100, model="deepseek-v4-flash"))
        r.add_usage(TokenUsage(prompt_tokens=200, model="deepseek-v4-pro"))
        assert r.request_count == 2
        assert r.total_cost > 0

    def test_router_reset_and_reuse(self) -> None:
        reset_router()
        r1 = get_router()
        r1.route("test query")
        reset_router()
        r2 = get_router()
        assert r2.get_metrics()["total_routed"] == 0
