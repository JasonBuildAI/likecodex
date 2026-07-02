"""SmartRouter — multi-model, multi-provider task router.

Automatically selects the optimal provider + model combination based on
task type, cost budget, and manual overrides.

Supported providers: ``deepseek``, ``claude``, ``ollama``
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────

class TaskType(str, Enum):
    """Task complexity classification."""
    A_SIMPLE_QA = "simple_qa"
    B_CODE_TASK = "code_task"
    C_COMPLEX_REASONING = "complex_reasoning"
    D_CREATIVE_ANALYSIS = "creative_analysis"


class ProviderType(str, Enum):
    """Supported LLM providers."""
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OLLAMA = "ollama"


# ── Data classes ──────────────────────────────────────────────

@dataclass
class ModelConfig:
    """A concrete provider + model combination."""
    provider: ProviderType
    model: str
    thinking: bool = False
    thinking_budget: int | None = None
    reasoning_effort: str = ""
    cost_per_call: float = 0.0  # estimated USD per call
    priority: int = 0


@dataclass
class RouterRule:
    """A routing rule with keyword matching and model assignment."""
    name: str
    keywords: list[str]
    task_type: TaskType
    model_config: ModelConfig
    priority: int = 0

    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return any(kw.lower() in query_lower for kw in self.keywords)


@dataclass
class RouterMetrics:
    """Metrics tracking for routing decisions."""
    total_routed: int = 0
    deepseek_count: int = 0
    claude_count: int = 0
    ollama_count: int = 0
    type_a_count: int = 0
    type_b_count: int = 0
    type_c_count: int = 0
    type_d_count: int = 0
    total_estimated_cost: float = 0.0
    last_routes: list[dict[str, Any]] = field(default_factory=list)
    max_history: int = 100

    def record(
        self,
        query: str,
        task_type: TaskType,
        model_config: ModelConfig,
        duration_ms: float,
    ) -> None:
        self.total_routed += 1
        if model_config.provider == ProviderType.DEEPSEEK:
            self.deepseek_count += 1
        elif model_config.provider == ProviderType.CLAUDE:
            self.claude_count += 1
        elif model_config.provider == ProviderType.OLLAMA:
            self.ollama_count += 1

        type_map = {
            TaskType.A_SIMPLE_QA: "type_a_count",
            TaskType.B_CODE_TASK: "type_b_count",
            TaskType.C_COMPLEX_REASONING: "type_c_count",
            TaskType.D_CREATIVE_ANALYSIS: "type_d_count",
        }
        setattr(self, type_map[task_type], getattr(self, type_map[task_type]) + 1)
        self.total_estimated_cost += model_config.cost_per_call

        self.last_routes.append({
            "query": query[:100],
            "task_type": task_type.value,
            "provider": model_config.provider.value,
            "model": model_config.model,
            "thinking": model_config.thinking,
            "duration_ms": round(duration_ms, 2),
            "estimated_cost": model_config.cost_per_call,
            "timestamp": time.time(),
        })
        if len(self.last_routes) > self.max_history:
            self.last_routes.pop(0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_routed": self.total_routed,
            "deepseek_count": self.deepseek_count,
            "claude_count": self.claude_count,
            "ollama_count": self.ollama_count,
            "type_a_count": self.type_a_count,
            "type_b_count": self.type_b_count,
            "type_c_count": self.type_c_count,
            "type_d_count": self.type_d_count,
            "total_estimated_cost": round(self.total_estimated_cost, 6),
            "last_50_routes": self.last_routes[-50:],
        }


# ── Default configs ───────────────────────────────────────────

# Model config presets
FAST_CHEAP = ModelConfig(
    provider=ProviderType.OLLAMA,
    model="llama3.2",
    cost_per_call=0.0,
    priority=0,
)

DEEPSEEK_FLASH = ModelConfig(
    provider=ProviderType.DEEPSEEK,
    model="deepseek-v4-flash",
    cost_per_call=0.0001,
    priority=10,
)

DEEPSEEK_PRO = ModelConfig(
    provider=ProviderType.DEEPSEEK,
    model="deepseek-v4-pro",
    cost_per_call=0.0005,
    priority=20,
)

DEEPSEEK_PRO_THINKING = ModelConfig(
    provider=ProviderType.DEEPSEEK,
    model="deepseek-v4-pro",
    thinking=True,
    reasoning_effort="high",
    cost_per_call=0.001,
    priority=30,
)

CLAUDE_SONNET = ModelConfig(
    provider=ProviderType.CLAUDE,
    model="claude-3-5-sonnet-latest",
    cost_per_call=0.003,
    priority=20,
)

CLAUDE_OPUS = ModelConfig(
    provider=ProviderType.CLAUDE,
    model="claude-3-opus-latest",
    thinking=True,
    thinking_budget=8192,
    cost_per_call=0.015,
    priority=30,
)

CLAUDE_HAIKU = ModelConfig(
    provider=ProviderType.CLAUDE,
    model="claude-3-5-haiku-latest",
    cost_per_call=0.0005,
    priority=10,
)


# Default routing rules — multi-provider aware
DEFAULT_RULES: list[RouterRule] = [
    # Type C: Complex reasoning (highest priority)
    RouterRule(
        name="complex_math",
        keywords=["prove", "theorem", "derivation", "mathematical", "equation system",
                   "calculus", "linear algebra", "optimization", "complexity"],
        task_type=TaskType.C_COMPLEX_REASONING,
        model_config=DEEPSEEK_PRO_THINKING,
        priority=30,
    ),
    RouterRule(
        name="architecture_design",
        keywords=["architecture", "design pattern", "system design", "scalability",
                   "trade-off", "decomposition", "refactoring plan"],
        task_type=TaskType.C_COMPLEX_REASONING,
        model_config=DEEPSEEK_PRO_THINKING,
        priority=29,
    ),
    RouterRule(
        name="deep_debug",
        keywords=["race condition", "memory leak", "deadlock", "concurrency bug",
                   "performance issue", "bottleneck", "crash analysis"],
        task_type=TaskType.C_COMPLEX_REASONING,
        model_config=CLAUDE_OPUS,
        priority=28,
    ),
    # Type B: Code tasks
    RouterRule(
        name="code_generation",
        keywords=["implement", "write a function", "create class", "add feature",
                   "new module", "code", "function", "method", "class"],
        task_type=TaskType.B_CODE_TASK,
        model_config=CLAUDE_SONNET,
        priority=20,
    ),
    RouterRule(
        name="code_debug",
        keywords=["fix", "bug", "error", "crash", "not working", "failing",
                   "exception", "wrong output"],
        task_type=TaskType.B_CODE_TASK,
        model_config=DEEPSEEK_PRO,
        priority=19,
    ),
    RouterRule(
        name="test_writing",
        keywords=["write test", "unit test", "integration test", "test case",
                   "pytest", "jest", "testing"],
        task_type=TaskType.B_CODE_TASK,
        model_config=CLAUDE_HAIKU,
        priority=18,
    ),
    RouterRule(
        name="code_review",
        keywords=["review", "code review", "refactor", "optimize", "clean up"],
        task_type=TaskType.B_CODE_TASK,
        model_config=DEEPSEEK_PRO,
        priority=17,
    ),
    # Type D: Creative & analysis
    RouterRule(
        name="creative_writing",
        keywords=["write a story", "poem", "essay", "creative", "blog post",
                   "documentation", "readme"],
        task_type=TaskType.D_CREATIVE_ANALYSIS,
        model_config=CLAUDE_HAIKU,
        priority=10,
    ),
    RouterRule(
        name="data_analysis",
        keywords=["analyze", "analysis", "statistics", "chart", "plot",
                   "visualization", "trend", "report"],
        task_type=TaskType.D_CREATIVE_ANALYSIS,
        model_config=DEEPSEEK_FLASH,
        priority=9,
    ),
    # Type A: Simple Q&A (lowest priority, catch-all)
    RouterRule(
        name="simple_qa",
        keywords=["what is", "what's", "explain", "meaning ", "definition",
                   "how to", "why is", "can you tell", "difference between"],
        task_type=TaskType.A_SIMPLE_QA,
        model_config=FAST_CHEAP,
        priority=5,
    ),
]


class SmartRouter:
    """Multi-provider smart router for LLM queries.

    Routes queries based on:
      - Keyword matching against rules
      - Maximum cost budget (if set, prefers cheaper models)
      - Manual override (``force_provider`` / ``force_model``)
    """

    def __init__(
        self,
        rules: list[RouterRule] | None = None,
        fallback_config: ModelConfig | None = None,
        custom_classifier: Callable[[str], TaskType | None] | None = None,
        *,
        max_cost_per_call: float | None = None,
    ) -> None:
        self.rules = rules or DEFAULT_RULES.copy()
        self.fallback_config = fallback_config or DEEPSEEK_FLASH
        self.custom_classifier = custom_classifier
        self.max_cost_per_call = max_cost_per_call  # if set, skip models exceeding this
        self.metrics = RouterMetrics()
        self._force_provider: ProviderType | None = None
        self._force_model: str | None = None

    # ------------------------------------------------------------------
    # Override API
    # ------------------------------------------------------------------

    def set_force_provider(self, provider: ProviderType | str | None) -> None:
        """Force the router to always use a specific provider.

        Pass ``None`` to clear the override.
        """
        if provider is None:
            self._force_provider = None
            return
        if isinstance(provider, str):
            provider = ProviderType(provider)
        self._force_provider = provider

    def set_force_model(self, model: str | None) -> None:
        """Force the router to always use a specific model.

        Pass ``None`` to clear the override.
        """
        self._force_model = model

    def clear_overrides(self) -> None:
        """Clear all manual overrides."""
        self._force_provider = None
        self._force_model = None

    @property
    def has_overrides(self) -> bool:
        return self._force_provider is not None or self._force_model is not None

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    def set_budget(self, max_cost_per_call: float | None) -> None:
        """Set the maximum cost per call in USD.

        The router will skip model configs that exceed this budget.
        Pass ``None`` to disable budget limit.
        """
        self.max_cost_per_call = max_cost_per_call

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, query: str) -> RouterRule:
        """Classify a query and return the best matching rule."""
        # Custom classifier takes precedence
        if self.custom_classifier:
            task_type = self.custom_classifier(query)
            if task_type:
                return RouterRule(
                    name="custom_classified",
                    keywords=[],
                    task_type=task_type,
                    model_config=self._best_config_for_type(task_type),
                    priority=100,
                )

        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            # Skip if exceeds budget
            if self.max_cost_per_call is not None and rule.model_config.cost_per_call > self.max_cost_per_call:
                continue
            # Skip if provider override is active and doesn't match
            if self._force_provider is not None and rule.model_config.provider != self._force_provider:
                continue
            if rule.matches(query):
                return rule

        return self._fallback_rule(query)

    def route(self, query: str) -> dict[str, Any]:
        """Route a query to the optimal model configuration.

        Returns a dict with keys:
          ``provider``, ``model``, ``task_type``, ``thinking``,
          ``reasoning_effort``, ``thinking_budget``, ``rule_name``
        """
        start = time.time()
        rule = self.classify(query)
        cfg = rule.model_config

        # Apply model override
        final_model = self._force_model or cfg.model

        result = {
            "query": query[:200],
            "task_type": rule.task_type.value,
            "provider": cfg.provider.value if self._force_provider is None else self._force_provider.value,
            "model": final_model,
            "thinking": cfg.thinking,
            "thinking_budget": cfg.thinking_budget,
            "reasoning_effort": cfg.reasoning_effort,
            "estimated_cost": cfg.cost_per_call,
            "rule_name": rule.name,
        }

        duration_ms = (time.time() - start) * 1000
        self.metrics.record(query, rule.task_type, cfg, duration_ms)

        return result

    def route_and_create_provider(self, query: str) -> dict[str, Any]:
        """Route a query and return kwargs suitable for ``create_provider()``.

        Returns the route dict with an additional ``provider_kwargs`` key
        that can be passed directly to ``factory.create_provider()``.
        """
        route = self.route(query)
        provider_kwargs: dict[str, Any] = {
            "provider": route["provider"],
            "model": route["model"],
        }
        if route.get("thinking"):
            provider_kwargs["thinking"] = True
            provider_kwargs["thinking_budget"] = route.get("thinking_budget")
            if route.get("reasoning_effort"):
                provider_kwargs["reasoning_effort"] = route["reasoning_effort"]
        route["provider_kwargs"] = provider_kwargs
        return route

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        return self.metrics.to_dict()

    def reset_metrics(self) -> None:
        self.metrics = RouterMetrics()

    # ------------------------------------------------------------------
    # Rules management
    # ------------------------------------------------------------------

    def add_rule(self, rule: RouterRule) -> None:
        self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                return True
        return False

    def get_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "name": r.name,
                "keywords": r.keywords,
                "task_type": r.task_type.value,
                "provider": r.model_config.provider.value,
                "model": r.model_config.model,
                "priority": r.priority,
                "thinking": r.model_config.thinking,
                "estimated_cost": r.model_config.cost_per_call,
            }
            for r in self.rules
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _best_config_for_type(self, task_type: TaskType) -> ModelConfig:
        """Find the best model config for a given task type."""
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            if rule.task_type == task_type:
                return rule.model_config
        return self.fallback_config

    def _fallback_rule(self, query: str) -> RouterRule:
        """Heuristic fallback when no rules match."""
        word_count = len(query.split())
        has_code = any(
            kw in query.lower()
            for kw in ["{", "}", "def ", "class ", "import ", "function",
                        "=>", "->", "const ", "let ", "var "]
        )
        has_math = any(
            kw in query.lower()
            for kw in ["=", "+", "-", "*", "/", "∑", "∫", "√"]
        )

        if has_code and word_count > 15:
            return RouterRule(
                name="fallback_code",
                keywords=[],
                task_type=TaskType.B_CODE_TASK,
                model_config=CLAUDE_SONNET,
                priority=0,
            )
        if has_math or word_count > 30:
            return RouterRule(
                name="fallback_complex",
                keywords=[],
                task_type=TaskType.C_COMPLEX_REASONING,
                model_config=DEEPSEEK_PRO_THINKING,
                priority=0,
            )
        return RouterRule(
            name="fallback_simple",
            keywords=[],
            task_type=TaskType.A_SIMPLE_QA,
            model_config=self.fallback_config,
            priority=0,
        )


# ── Global singleton ──────────────────────────────────────────

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
