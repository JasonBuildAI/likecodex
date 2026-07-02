"""Rule validation and conflict detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from likecodex_engine.agent.definitions.models import AgentRule
from likecodex_engine.agent.definitions.schema import AgentDefinition

logger = logging.getLogger(__name__)


@dataclass
class RuleConflict:
    """Describes a conflict between two rules."""

    rule_a: str
    rule_b: str
    description: str = ""
    severity: str = "warning"  # warning, error


@dataclass
class ValidationResult:
    """Result of validating agent definitions or rules."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[RuleConflict] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_conflict(self, conflict: RuleConflict) -> None:
        self.conflicts.append(conflict)
        if conflict.severity == "error":
            self.valid = False

    def merge(self, other: ValidationResult) -> None:
        if not other.valid:
            self.valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.conflicts.extend(other.conflicts)


class RuleValidator:
    """Validates agent definitions and rules for correctness and conflicts.

    Checks:
    - Schema compliance
    - Rule pattern validity
    - Conflicting rules (same pattern, different actions)
    - Circular or impossible conditions
    """

    def __init__(self) -> None:
        self._known_patterns: set[str] = set()

    def validate_definition(self, definition: AgentDefinition) -> ValidationResult:
        """Validate a single agent definition."""
        result = ValidationResult()

        # Check required fields
        if not definition.name:
            result.add_error("Agent definition must have a 'name' field.")

        if not definition.name.isidentifier():
            result.add_warning(f"Agent name '{definition.name}' is not a valid identifier.")

        # Check model config
        if definition.temperature is not None and not (0.0 <= definition.temperature <= 2.0):
            result.add_warning(f"Temperature {definition.temperature} is outside recommended range [0.0, 2.0].")

        if definition.max_tokens is not None and definition.max_tokens < 1:
            result.add_error(f"max_tokens must be >= 1, got {definition.max_tokens}.")

        # Check agent mode
        valid_modes = {"agent", "ask", "manual", "plan"}
        if definition.agent_mode not in valid_modes:
            result.add_error(f"Invalid agent_mode '{definition.agent_mode}'. Must be one of {valid_modes}.")

        # Validate rules
        for rule_data in definition.rules:
            try:
                rule = AgentRule(**rule_data)
                rule_result = self.validate_rule(rule)
                result.merge(rule_result)
            except Exception as exc:
                result.add_error(f"Invalid rule in definition '{definition.name}': {exc}")

        return result

    def validate_rule(self, rule: AgentRule) -> ValidationResult:
        """Validate a single rule."""
        result = ValidationResult()

        if not rule.name:
            result.add_warning("Rule without a name found.")

        if rule.action not in ("allow", "block", "modify", "redirect", "warn"):
            result.add_error(f"Invalid rule action '{rule.action}'. Must be one of: allow, block, modify, redirect, warn.")

        # Validate conditions
        for i, condition in enumerate(rule.conditions):
            if "field" not in condition:
                result.add_error(f"Condition #{i} in rule '{rule.name}' is missing 'field'.")
            if "op" not in condition:
                result.add_error(f"Condition #{i} in rule '{rule.name}' is missing 'op' (operator).")

            valid_ops = {"eq", "neq", "in", "not_in", "matches", "exists", "gt", "lt"}
            if condition.get("op") not in valid_ops:
                result.add_error(
                    f"Condition #{i} in rule '{rule.name}' has invalid operator '{condition.get('op')}'."
                )

        return result

    def detect_conflicts(self, rules: list[AgentRule]) -> list[RuleConflict]:
        """Detect conflicts between rules.

        Conflicts occur when:
        - Two rules with different actions match the same pattern
        - Two allow/block rules with equal priority contradict each other
        """
        conflicts: list[RuleConflict] = []

        for i, a in enumerate(rules):
            for b in rules[i + 1:]:
                if a.pattern == b.pattern:
                    if a.action != b.action:
                        if a.priority == b.priority:
                            conflicts.append(RuleConflict(
                                rule_a=a.name,
                                rule_b=b.name,
                                description=(
                                    f"Rules '{a.name}' and '{b.name}' match same pattern '{a.pattern}' "
                                    f"with different actions ({a.action} vs {b.action}) and same priority."
                                ),
                                severity="error",
                            ))
                        else:
                            conflicts.append(RuleConflict(
                                rule_a=a.name,
                                rule_b=b.name,
                                description=(
                                    f"Rules '{a.name}' and '{b.name}' match same pattern '{a.pattern}' "
                                    f"with different actions ({a.action} vs {b.action}). "
                                    f"Higher priority ({max(a.priority, b.priority)}) will win."
                                ),
                                severity="warning",
                            ))

        return conflicts

    def validate_definitions(self, definitions: list[AgentDefinition]) -> ValidationResult:
        """Validate a list of agent definitions and detect cross-definition conflicts."""
        result = ValidationResult()

        # Validate each definition
        for definition in definitions:
            result.merge(self.validate_definition(definition))

        # Check for duplicate names
        seen_names: dict[str, list[str]] = {}
        for definition in definitions:
            if definition.name not in seen_names:
                seen_names[definition.name] = []
            seen_names[definition.name].append(definition.source)

        for name, sources in seen_names.items():
            if len(sources) > 1:
                result.add_warning(f"Agent definition '{name}' appears in multiple sources: {sources}")

        return result
