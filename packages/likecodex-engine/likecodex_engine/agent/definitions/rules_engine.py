"""Rules engine for executing behavioral rules on agent operations."""

from __future__ import annotations

import fnmatch
import re
from typing import Any

from likecodex_engine.agent.definitions.models import AgentRule


class RulesEngine:
    """Executes behavioral rules against agent actions.

    Supports pattern matching, allow/block decisions,
    and automatic actions based on rule conditions.
    """

    def __init__(self) -> None:
        self._rules: list[AgentRule] = []

    def load_rules(self, rules: list[AgentRule]) -> None:
        """Replace current rules with a new set."""
        self._rules = list(rules)

    def add_rule(self, rule: AgentRule) -> None:
        """Add a single rule."""
        self._rules.append(rule)

    @property
    def rules(self) -> list[AgentRule]:
        return list(self._rules)

    def evaluate(self, action: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Evaluate all rules against the given action and context.

        Args:
            action: The action being taken (e.g., tool name, event type).
            context: Optional context dict for condition evaluation.

        Returns:
            List of matching rule results with decisions.
        """
        results: list[dict[str, Any]] = []
        ctx = context or {}

        for rule in self._rules:
            if not rule.enabled:
                continue
            if not self._matches_pattern(action, rule.pattern):
                continue
            if not self._evaluate_conditions(rule.conditions, ctx):
                continue

            results.append({
                "rule_name": rule.name,
                "pattern": rule.pattern,
                "action": rule.action,
                "priority": rule.priority,
                "params": rule.params,
                "metadata": rule.metadata,
            })

        # Sort by priority (highest first)
        results.sort(key=lambda r: r["priority"], reverse=True)
        return results

    def is_allowed(self, action: str, context: dict[str, Any] | None = None) -> bool:
        """Check if an action is allowed based on rules.

        Returns False if any matching rule has action='block'.
        Returns True if no rules match or matching rules allow.
        """
        results = self.evaluate(action, context)
        if not results:
            return True
        # Check in priority order; any 'block' action denies
        return not any(r["action"] == "block" for r in results)

    def get_effective_tools(self, requested_tools: list[str], context: dict[str, Any] | None = None) -> list[str]:
        """Filter a list of tool names based on rules."""
        allowed: list[str] = []
        ctx = context or {}

        for tool in requested_tools:
            results = self.evaluate(tool, ctx)
            if not results:
                allowed.append(tool)
                continue
            # Highest priority rule wins
            top = results[0]
            if top["action"] == "allow":
                allowed.append(tool)
            elif top["action"] == "block":
                continue  # skip blocked tools
            elif top["action"] == "modify":
                # Modify the tool based on params
                if top.get("params", {}).get("keep"):
                    allowed.append(tool)
                # else drop it
            elif top["action"] == "redirect":
                # Redirect to another tool
                redirect_to = top.get("params", {}).get("redirect_to", tool)
                if redirect_to not in allowed:
                    allowed.append(redirect_to)

        return allowed

    def clear(self) -> None:
        """Remove all rules."""
        self._rules.clear()

    def _matches_pattern(self, action: str, pattern: str) -> bool:
        """Check if an action matches a pattern (supports glob)."""
        if pattern == "*":
            return True
        if fnmatch.fnmatch(action, pattern):
            return True
        return False

    def _evaluate_conditions(self, conditions: list[dict[str, Any]], context: dict[str, Any]) -> bool:
        """Evaluate if all conditions are met."""
        if not conditions:
            return True

        for condition in conditions:
            if not self._evaluate_single_condition(condition, context):
                return False
        return True

    def _evaluate_single_condition(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        """Evaluate a single condition against context.

        Supported condition operators: eq, neq, in, not_in, matches, exists, gt, lt.
        """
        field = condition.get("field", "")
        operator = condition.get("op", "eq")
        value = condition.get("value")

        # Get actual value from context
        actual = self._get_nested_value(context, field)

        if operator == "exists":
            return actual is not None
        if operator == "eq":
            return actual == value
        if operator == "neq":
            return actual != value
        if operator == "in":
            return actual in (value or [])
        if operator == "not_in":
            return actual not in (value or [])
        if operator == "matches":
            if isinstance(value, str) and isinstance(actual, str):
                return bool(re.search(value, actual))
            return False
        if operator == "gt":
            if actual is not None and value is not None:
                return float(actual) > float(value)
            return False
        if operator == "lt":
            if actual is not None and value is not None:
                return float(actual) < float(value)
            return False
        return True

    @staticmethod
    def _get_nested_value(context: dict[str, Any], field: str) -> Any:
        """Get a nested value from context using dot notation."""
        parts = field.split(".")
        current: Any = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
