"""SmartRouter — task-type-based model routing for DeepSeek V4.

Automatically routes user queries to the optimal model:
- Type A: Simple Q&A → DeepSeek Flash (fast, cheap)
- Type B: Code generation/debugging → DeepSeek Pro (powerful)
- Type C: Complex reasoning → DeepSeek Pro with thinking
- Type D: Creative writing/analysis → DeepSeek Flash (sufficient)

Configurable routing rules with metrics tracking.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Four-level task type classification."""

    A_SIMPLE_QA = "simple_qa"
    B_CODE_TASK = "code_task"
    C_COMPLEX_REASONING = "complex_reasoning"
    D_CREATIVE_ANALYSIS = "creative_analysis"


class ModelChoice(str, Enum):
    FLASH = "deepseek-v4-flash"
    PRO = "deepseek-v4-pro"
    PRO_THINKING = "deepseek-v4-pro-thinking"


@dataclass
class RouterRule:
    """A single routing rule with pattern matching."""

    name: str
    keywords: list[str]
    task_type: TaskType
    model: ModelChoice
    priority: int = 0
    thinking: bool = False
    reasoning_effort: str = "medium"

    def matches(self, query: str) -> bool:
        """Check if the query matches this rule's keywords."""
        query_lower = query.lower()
        return any(kw.lower() in query_lower for kw in self.keywords)


@dataclass
class RouterMetrics:
    """Metrics for router decisions."""

    total_routed: int = 0
    flash_count: int = 0
    pro_count: int = 0
    pro_thinking_count: int = 0
    type_a_count: int = 0
    type_b_count: int = 0
    type_c_count: int = 0
    type_d_count: int = 0
    last_routes: list[dict[str, Any]] = field(default_factory=list)
    max_history: int = 100

    def record(
        self,
        query: str,
        task_type: TaskType,
        model: ModelChoice,
        duration_ms: float,
    ) -> None:
        self.total_routed += 1
        if model == ModelChoice.FLASH:
            self.flash_count += 1
        elif model == ModelChoice.PRO:
            self.pro_count += 1
        elif model == ModelChoice.PRO_THINKING:
            self.pro_thinking_count += 1

        type_map = {
            TaskType.A_SIMPLE_QA: "type_a_count",
            TaskType.B_CODE_TASK: "type_b_count",
            TaskType.C_COMPLEX_REASONING: "type_c_count",
            TaskType.D_CREATIVE_ANALYSIS: "type_d_count",
        }
        setattr(self, type_map[task_type], getattr(self, type_map[task_type]) + 1)

        self.last_routes.append({
            "query": query[:100],
            "task_type": task_type.value,
            "model": model.value,
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.time(),
        })
        if len(self.last_routes) > self.max_history:
            self.last_routes.pop(0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_routed": self.total_routed,
            "flash_count": self.flash_count,
            "pro_count": self.pro_count,
            "pro_thinking_count": self.pro_thinking_count,
            "type_a_count": self.type_a_count,
            "type_b_count": self.type_b_count,
            "type_c_count": self.type_c_count,
            "type_d_count": self.type_d_count,
            "last_50_routes": self.last_routes[-50:],
        }


# Default routing rules
DEFAULT_RULES: list[RouterRule] = [
    # Type C: Complex reasoning (highest priority)
    RouterRule(
        name="complex_math",
        keywords=["prove", "theorem", "derivation", "mathematical", "equation system",
                   "calculus", "linear algebra", "optimization", "complexity"],
        task_type=TaskType.C_COMPLEX_REASONING,
        model=ModelChoice.PRO_THINKING,
        priority=30,
        thinking=True,
        reasoning_effort="high",
    ),
    RouterRule(
        name="architecture_design",
        keywords=["architecture", "design pattern", "system design", "scalability",
                   "trade-off", "decomposition", "refactoring plan"],
        task_type=TaskType.C_COMPLEX_REASONING,
        model=ModelChoice.PRO_THINKING,
        priority=29,
        thinking=True,
        reasoning_effort="high",
    ),
    RouterRule(
        name="deep_debug",
        keywords=["race condition", "memory leak", "deadlock", "concurrency bug",
                   "performance issue", "bottleneck", "crash analysis"],
        task_type=TaskType.C_COMPLEX_REASONING,
        model=ModelChoice.PRO_THINKING,
        priority=28,
        thinking=True,
        reasoning_effort="high",
    ),
    # Type B: Code tasks
    RouterRule(
        name="code_generation",
        keywords=["implement", "write a function", "create class", "add feature",
                   "new module", "code", "function", "method", "class"],
        task_type=TaskType.B_CODE_TASK,
        model=ModelChoice.PRO,
        priority=20,
    ),
    RouterRule(
        name="code_debug",
        keywords=["fix", "bug", "error", "crash", "not working", "failing",
                   "exception", "wrong output"],
        task_type=TaskType.B_CODE_TASK,
        model=ModelChoice.PRO,
        priority=19,
    ),
    RouterRule(
        name="test_writing",
        keywords=["write test", "unit test", "integration test", "test case",
                   "pytest", "jest", "testing"],
        task_type=TaskType.B_CODE_TASK,
        model=ModelChoice.FLASH,
        priority=18,
    ),
    RouterRule(
        name="code_review",
        keywords=["review", "code review", "refactor", "optimize", "clean up"],
        task_type=TaskType.B_CODE_TASK,
        model=ModelChoice.PRO,
        priority=17,
    ),
    # Type D: Creative & analysis
    RouterRule(
        name="creative_writing",
        keywords=["write a story", "poem", "essay", "creative", "blog post",
                   "documentation", "readme"],
        task_type=TaskType.D_CREATIVE_ANALYSIS,
        model=ModelChoice.FLASH,
        priority=10,
    ),
    RouterRule(
        name="data_analysis",
        keywords=["analyze", "analysis", "statistics", "chart", "plot",
                   "visualization", "trend", "report"],
        task_type=TaskType.D_CREATIVE_ANALYSIS,
        model=ModelChoice.FLASH,
        priority=9,
    ),
    # Type A: Simple Q&A (lowest priority, catch-all)
    RouterRule(
        name="simple_qa",
        keywords=["what is", "what's", "explain", "meaning ", "definition",
                   "how to", "why is", "can you tell", "difference between"],
        task_type=TaskType.A_SIMPLE_QA,
        model=ModelChoice.FLASH,
        priority=5,
    ),
]


class SmartRouter:
    """Routes queries to the optimal DeepSeek model based on task type."""

    def __init__(
        self,
        rules: list[RouterRule] | None = None,
        fallback_model: ModelChoice = ModelChoice.FLASH,
        custom_classifier: Callable[[str], TaskType | None] | None = None,
    ):
        self.rules = rules or DEFAULT_RULES.copy()
        self.fallback_model = fallback_model
        self.custom_classifier = custom_classifier
        self.metrics = RouterMetrics()

    def classify(self, query: str) -> RouterRule:
        """Classify a query and return the matching rule (highest priority first)."""
        # Try custom classifier first
        if self.custom_classifier:
            task_type = self.custom_classifier(query)
            if task_type:
                return RouterRule(
                    name="custom_classified",
                    keywords=[],
                    task_type=task_type,
                    model=self._model_for_type(task_type),
                    priority=100,
                )

        # Sort rules by priority descending
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if rule.matches(query):
                return rule

        # Fallback: classify by query length & complexity heuristics
        return self._fallback_rule(query)

    def route(self, query: str) -> dict[str, Any]:
        """Route a query to the optimal model configuration."""
        start = time.time()
        rule = self.classify(query)

        result = {
            "query": query[:200],
            "task_type": rule.task_type.value,
            "model": rule.model.value,
            "thinking": rule.thinking,
            "reasoning_effort": rule.reasoning_effort,
            "rule_name": rule.name,
        }

        duration_ms = (time.time() - start) * 1000
        self.metrics.record(query, rule.task_type, rule.model, duration_ms)

        return result

    def route_and_create_provider(self, query: str) -> dict[str, Any]:
        """Route a query and create provider kwargs for the selected model."""
        route = self.route(query)
        provider_kwargs: dict[str, Any] = {
            "provider": "deepseek",
            "model": route["model"],
        }
        if route.get("thinking"):
            provider_kwargs["thinking"] = True
            provider_kwargs["reasoning_effort"] = route.get("reasoning_effort", "medium")
        route["provider_kwargs"] = provider_kwargs
        return route

    def get_metrics(self) -> dict[str, Any]:
        """Get current router metrics."""
        return self.metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self.metrics = RouterMetrics()

    def add_rule(self, rule: RouterRule) -> None:
        """Add a custom routing rule."""
        self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                return True
        return False

    def get_rules(self) -> list[dict[str, Any]]:
        """Get all rules as dicts."""
        return [
            {
                "name": r.name,
                "keywords": r.keywords,
                "task_type": r.task_type.value,
                "model": r.model.value,
                "priority": r.priority,
                "thinking": r.thinking,
            }
            for r in self.rules
        ]

    def _model_for_type(self, task_type: TaskType) -> ModelChoice:
        """Map task type to default model."""
        mapping = {
            TaskType.A_SIMPLE_QA: ModelChoice.FLASH,
            TaskType.B_CODE_TASK: ModelChoice.PRO,
            TaskType.C_COMPLEX_REASONING: ModelChoice.PRO_THINKING,
            TaskType.D_CREATIVE_ANALYSIS: ModelChoice.FLASH,
        }
        return mapping.get(task_type, self.fallback_model)

    def _fallback_rule(self, query: str) -> RouterRule:
        """Heuristic fallback when no rules match."""
        word_count = len(query.split())
        has_code_indicators = any(
            kw in query.lower()
            for kw in ["{", "}", "def ", "class ", "import ", "function",
                        "=>", "->", "const ", "let ", "var "]
        )
        has_math_indicators = any(
            kw in query.lower()
            for kw in ["=", "+", "-", "*", "/", "∑", "∫", "√"]
        )

        if has_code_indicators and word_count > 15:
            return RouterRule(
                name="fallback_code",
                keywords=[],
                task_type=TaskType.B_CODE_TASK,
                model=ModelChoice.PRO,
                priority=0,
            )
        if has_math_indicators or word_count > 30:
            return RouterRule(
                name="fallback_complex",
                keywords=[],
                task_type=TaskType.C_COMPLEX_REASONING,
                model=ModelChoice.PRO_THINKING,
                priority=0,
                thinking=True,
                reasoning_effort="medium",
            )
        return RouterRule(
            name="fallback_simple",
            keywords=[],
            task_type=TaskType.A_SIMPLE_QA,
            model=self.fallback_model,
            priority=0,
        )


# Global singleton
_global_router: SmartRouter | None = None


def get_router() -> SmartRouter:
    """Get or create the global SmartRouter instance."""
    global _global_router
    if _global_router is None:
        _global_router = SmartRouter()
    return _global_router


def reset_router() -> None:
    """Reset the global router instance."""
    global _global_router
    _global_router = None
