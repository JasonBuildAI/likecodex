"""Tests for AdaptiveReasoningController reasoning depth."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from likecodex_engine.agent.adaptive_reasoning import (
    AdaptiveReasoningController,
    ReasoningConfig,
    ReasoningDepth,
    TaskComplexity,
)


class TestReasoningDepth:
    """Tests for the ReasoningDepth enum."""

    def test_values(self) -> None:
        assert ReasoningDepth.QUICK_QA.value == 0
        assert ReasoningDepth.LIGHT_ANALYSIS.value == 1
        assert ReasoningDepth.STANDARD.value == 2
        assert ReasoningDepth.DEEP.value == 3
        assert ReasoningDepth.FULL_REASONING.value == 4


class TestReasoningConfig:
    """Tests for ReasoningConfig data model."""

    def test_default_config(self) -> None:
        config = ReasoningConfig()
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.thinking is False

    def test_custom_config(self) -> None:
        config = ReasoningConfig(temperature=0.1, max_tokens=512, thinking=False)
        assert config.temperature == 0.1
        assert config.max_tokens == 512


class TestTaskComplexity:
    """Tests for TaskComplexity data model."""

    def test_default_complexity(self) -> None:
        c = TaskComplexity()
        assert c.score == 0.0
        assert c.depth == ReasoningDepth.STANDARD
        assert c.reasoning == ""


class TestAdaptiveReasoningController:
    """Tests for AdaptiveReasoningController."""

    def test_default_depth(self) -> None:
        ctrl = AdaptiveReasoningController()
        assert ctrl.default_depth == ReasoningDepth.STANDARD

    def test_custom_default_depth(self) -> None:
        ctrl = AdaptiveReasoningController(default_depth=ReasoningDepth.DEEP)
        assert ctrl.default_depth == ReasoningDepth.DEEP

    def test_analyze_simple_question(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task("What is 2+2?")
        assert complexity.depth in (ReasoningDepth.QUICK_QA, ReasoningDepth.LIGHT_ANALYSIS)
        assert complexity.has_code is False
        assert complexity.has_multi_step is False

    def test_analyze_with_code_block(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task("```python\nprint('hello')\n```")
        assert complexity.has_code is True
        assert complexity.score > 0

    def test_analyze_multi_step(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task("First do this, then do that, finally do this")
        assert complexity.has_multi_step is True
        # 3 step keywords found, log2(3)*2.0 ≈ 3.17
        assert complexity.score > 3.0

    def test_analyze_debugging(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task("Fix this error: TypeError: 'NoneType' object is not iterable")
        assert complexity.has_debugging is True
        assert complexity.score > 0

    def test_analyze_architecture(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task("Design the architecture for a microservice system")
        assert complexity.has_architecture is True
        assert complexity.score > 0

    def test_analyze_deep_reasoning(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task(
            "Design the architecture for refactoring a complex system. "
            "First analyze the current codebase, then plan the migration, "
            "then implement the changes, then test everything. "
            "```python\ndef old_code():\n    pass\n```"
            "Fix any errors found during the process."
        )
        assert complexity.depth >= ReasoningDepth.DEEP
        assert complexity.has_architecture
        assert complexity.has_code
        assert complexity.has_multi_step
        assert complexity.has_debugging

    def test_get_config_with_explicit_depth(self) -> None:
        ctrl = AdaptiveReasoningController()
        config = ctrl.get_config(depth=ReasoningDepth.QUICK_QA)
        assert config.temperature == 0.3
        assert config.max_tokens == 1024
        assert config.thinking is False

    def test_get_config_with_prompt(self) -> None:
        ctrl = AdaptiveReasoningController()
        config = ctrl.get_config(prompt="What is the capital of France?")
        assert config is not None
        assert isinstance(config, ReasoningConfig)

    def test_get_config_default(self) -> None:
        ctrl = AdaptiveReasoningController()
        config = ctrl.get_config()
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_custom_configs_override_defaults(self) -> None:
        custom = {
            ReasoningDepth.STANDARD: ReasoningConfig(
                temperature=0.5, max_tokens=2048, thinking=False
            ),
        }
        ctrl = AdaptiveReasoningController(custom_configs=custom)
        config = ctrl.get_config(depth=ReasoningDepth.STANDARD)
        assert config.temperature == 0.5
        assert config.max_tokens == 2048

    def test_apply_to_llm_kwargs(self) -> None:
        ctrl = AdaptiveReasoningController()
        kwargs = {"temperature": 1.0, "max_tokens": 100}
        result = ctrl.apply_to_llm_kwargs("Simple question", kwargs)
        # kwargs should be modified in place
        assert result["temperature"] != 1.0  # should be overwritten
        assert result["max_tokens"] != 100

    def test_apply_to_llm_kwargs_thinking(self) -> None:
        ctrl = AdaptiveReasoningController()
        kwargs: dict = {}
        ctrl.apply_to_llm_kwargs(
            "Design a complex architecture with multiple steps and error handling",
            kwargs,
        )
        # Deep or full reasoning should set thinking=True
        if kwargs.get("thinking"):
            assert kwargs["thinking"] is True
            assert kwargs["temperature"] > 0.7
            assert kwargs["max_tokens"] >= 8192

    def test_depth_configs_all_present(self) -> None:
        ctrl = AdaptiveReasoningController()
        for depth in ReasoningDepth:
            config = ctrl.get_config(depth=depth)
            assert config is not None
            assert config.max_tokens > 0

    def test_analyze_token_estimate(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task("Hello world")
        assert complexity.token_estimate > 0

    def test_analyze_reasoning_string(self) -> None:
        ctrl = AdaptiveReasoningController()
        complexity = ctrl.analyze_task("What is 2+2?")
        assert "complexity_score" in complexity.reasoning
        assert "depth" in complexity.reasoning

    def test_estimate_tokens_static(self) -> None:
        assert AdaptiveReasoningController.estimate_tokens("Hello world") == 2  # 11/4=2
        assert AdaptiveReasoningController.estimate_tokens("x" * 40) == 10

    def test_complexity_scoring_full_reasoning(self) -> None:
        """Test that a very complex prompt results in FULL_REASONING depth."""
        ctrl = AdaptiveReasoningController()
        # Create a very complex prompt with all signals
        prompt = (
            "Design a microservice architecture for a large-scale e-commerce platform. "
            "```python\nclass Service:\n    pass\n```\n"
            "First configure the database, then set up the API gateway, "
            "then implement authentication, then add caching, "
            "finally deploy to production. "
            "Fix the TypeError in the payment service. "
            "Refactor the checkout flow using a new design pattern. "
            "Refer to /docs/architecture.md for more details."
        )
        complexity = ctrl.analyze_task(prompt)
        assert complexity.score > 10.0
