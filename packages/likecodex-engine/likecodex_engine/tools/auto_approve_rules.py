"""Auto-approve rules for batch tool-call automation.

Provides a rule engine that decides whether a tool call (or batch of tool
calls) can be automatically approved without user interaction.  This is the
core mechanism that makes Agent mode "fully automatic" — by defining which
tools and patterns are safe to approve unconditionally.

Mirrors Cursor's "auto-approve" behaviour where common, low-risk operations
(tests, linters, formatters, reads) run without prompting.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RuleAction(StrEnum):
    """What to do when a rule matches."""
    APPROVE = "approve"   # Auto-approve without asking
    DENY = "deny"         # Always deny
    ASK = "ask"           # Always ask user


class RuleScope(StrEnum):
    """How broadly a rule applies."""
    GLOBAL = "global"       # Applies everywhere
    PROJECT = "project"     # Only in the current project
    SESSION = "session"     # Only for the current session


# ---------------------------------------------------------------------------
# BatchRule
# ---------------------------------------------------------------------------

@dataclass
class BatchRule:
    """A single auto-approve / deny / ask rule.

    Attributes
    ----------
    name:
        Human-readable rule identifier.
    tool_pattern:
        Glob pattern matching tool names (e.g. ``"edit_*"``, ``"*"``).
    command_pattern:
        Optional regex or glob pattern for the shell command (only relevant
        for ``run_command``).
    path_pattern:
        Optional glob pattern for the file path argument.
    action:
        What to do when the rule matches.
    scope:
        How broadly the rule applies.
    priority:
        Higher-priority rules are evaluated first.  Ties broken by
        insertion order.
    enabled:
        Whether the rule is currently active.
    description:
        Optional human-readable description.
    hit_count:
        Number of times this rule has matched (for diagnostics).
    """

    name: str
    tool_pattern: str = "*"
    command_pattern: str | None = None
    path_pattern: str | None = None
    action: RuleAction = RuleAction.APPROVE
    scope: RuleScope = RuleScope.GLOBAL
    priority: int = 0
    enabled: bool = True
    description: str = ""
    hit_count: int = 0

    # Compiled regex (lazy)
    _cmd_regex: re.Pattern[str] | None = field(default=None, init=False, repr=False)

    def matches(self, tool_name: str, arguments: dict[str, Any] | None = None) -> bool:
        """Return *True* if this rule matches the given tool call."""
        if not self.enabled:
            return False

        arguments = arguments or {}

        # 1. Tool name match
        if not fnmatch.fnmatch(tool_name, self.tool_pattern):
            return False

        # 2. Command pattern (only for run_command)
        if self.command_pattern and tool_name == "run_command":
            cmd = str(arguments.get("command", ""))
            if not self._match_command(cmd):
                return False

        # 3. Path pattern
        if self.path_pattern:
            path = self._extract_path(arguments)
            if path is None or not fnmatch.fnmatch(path, self.path_pattern):
                return False

        return True

    def record_hit(self) -> None:
        self.hit_count += 1

    # -- Internal -----------------------------------------------------------

    def _match_command(self, cmd: str) -> bool:
        if self._cmd_regex is None and self.command_pattern:
            try:
                self._cmd_regex = re.compile(self.command_pattern)
            except re.error:
                logger.warning("Invalid command_pattern regex: %s", self.command_pattern)
                self._cmd_regex = re.compile("")  # never matches
        if self._cmd_regex:
            return bool(self._cmd_regex.search(cmd))
        return True

    @staticmethod
    def _extract_path(arguments: dict[str, Any]) -> str | None:
        return next(
            (str(arguments[k]) for k in ("path", "file_path", "source_path", "pattern") if k in arguments),
            None,
        )


# ---------------------------------------------------------------------------
# Built-in rule presets
# ---------------------------------------------------------------------------

def _default_rules() -> list[BatchRule]:
    """Return the default set of auto-approve rules (Cursor-parity)."""
    return [
        # --- Always approve: read-only tools ---
        BatchRule(
            name="allow-all-reads",
            tool_pattern="*",
            action=RuleAction.APPROVE,
            priority=100,
            description="Read-only tools are always auto-approved",
        ),

        # --- Approve: common safe shell commands ---
        BatchRule(
            name="allow-test-runners",
            tool_pattern="run_command",
            command_pattern=r"^(pytest|python\s+-m\s+pytest|go\s+test|cargo\s+test|npm\s+test|yarn\s+test|vitest|jest|mocha)\b",
            action=RuleAction.APPROVE,
            priority=90,
            description="Test runners are auto-approved in Agent mode",
        ),
        BatchRule(
            name="allow-linters",
            tool_pattern="run_command",
            command_pattern=r"^(ruff|flake8|pylint|mypy|eslint|prettier|black|isort|cargo\s+clippy|cargo\s+fmt|gofmt|goimports)\b",
            action=RuleAction.APPROVE,
            priority=90,
            description="Linters and formatters are auto-approved",
        ),
        BatchRule(
            name="allow-git-read",
            tool_pattern="run_command",
            command_pattern=r"^git\s+(status|diff|log|branch|show|blame|remote|stash\s+list)\b",
            action=RuleAction.APPROVE,
            priority=85,
            description="Git read-only commands are auto-approved",
        ),
        BatchRule(
            name="allow-build-tools",
            tool_pattern="run_command",
            command_pattern=r"^(make|cmake|cargo\s+build|go\s+build|npm\s+run\s+build|yarn\s+build|pip\s+install|uv\s+(sync|pip|add))\b",
            action=RuleAction.APPROVE,
            priority=80,
            description="Build tools are auto-approved",
        ),

        # --- Deny: dangerous operations ---
        BatchRule(
            name="deny-dangerous-shell",
            tool_pattern="run_command",
            command_pattern=r"(rm\s+-rf\s+/|mkfs|dd\s+if=|:\(\)\s*\{|chmod\s+-R\s+777\s+/|curl.*\|\s*sh|wget.*\|\s*sh)",
            action=RuleAction.DENY,
            priority=200,
            description="Block obviously dangerous shell commands",
        ),
        BatchRule(
            name="deny-git-force-push",
            tool_pattern="run_command",
            command_pattern=r"git\s+push\s+--force",
            action=RuleAction.DENY,
            priority=200,
            description="Block force-push to prevent history rewrite",
        ),
        BatchRule(
            name="deny-git-hard-reset",
            tool_pattern="run_command",
            command_pattern=r"git\s+reset\s+--hard",
            action=RuleAction.DENY,
            priority=200,
            description="Block hard reset to prevent data loss",
        ),

        # --- Ask: write tools that aren't covered by approvals ---
        BatchRule(
            name="ask-git-write",
            tool_pattern="run_command",
            command_pattern=r"^git\s+(commit|merge|rebase|cherry-pick|push)\b",
            action=RuleAction.ASK,
            priority=50,
            description="Git write operations require confirmation",
        ),
    ]


# ---------------------------------------------------------------------------
# AutoApproveRules
# ---------------------------------------------------------------------------

# Type alias for callbacks fired when a rule matches.
RuleMatchCallback = Callable[[BatchRule, str, dict[str, Any]], None]


class AutoApproveRules:
    """Rule engine that evaluates tool calls against an ordered list of
    :class:`BatchRule` instances.

    Rules are evaluated in priority order (highest first).  The first match
    wins.

    Parameters
    ----------
    rules:
        Initial rule set.  Defaults to the built-in presets.
    """

    def __init__(self, rules: list[BatchRule] | None = None) -> None:
        self._rules: list[BatchRule] = rules if rules is not None else _default_rules()
        self._sort_rules()
        self._match_callbacks: list[RuleMatchCallback] = []
        self._stats: dict[str, int] = {"total_evaluations": 0, "approved": 0, "denied": 0, "ask": 0, "no_match": 0}

    # -- Rule management ----------------------------------------------------

    @property
    def rules(self) -> list[BatchRule]:
        """Current rule set (sorted by priority, highest first)."""
        return list(self._rules)

    def add_rule(self, rule: BatchRule) -> None:
        """Add a rule and re-sort by priority."""
        self._rules.append(rule)
        self._sort_rules()

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.  Returns *True* if found and removed."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def enable_rule(self, name: str, enabled: bool = True) -> bool:
        """Enable or disable a rule by name."""
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = enabled
                return True
        return False

    def get_rule(self, name: str) -> BatchRule | None:
        return next((r for r in self._rules if r.name == name), None)

    # -- Evaluation ---------------------------------------------------------

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> RuleAction | None:
        """Evaluate *tool_name* against the rule set.

        Returns the :class:`RuleAction` of the first matching rule, or
        ``None`` if no rule matches.
        """
        arguments = arguments or {}
        self._stats["total_evaluations"] += 1

        for rule in self._rules:
            if rule.matches(tool_name, arguments):
                rule.record_hit()
                self._fire_match_callbacks(rule, tool_name, arguments)
                # Update stats
                key = rule.action.value
                self._stats[key] = self._stats.get(key, 0) + 1
                logger.debug("Rule %r matched %s → %s", rule.name, tool_name, rule.action.value)
                return rule.action

        self._stats["no_match"] += 1
        return None

    def evaluate_batch(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
    ) -> list[tuple[str, RuleAction | None]]:
        """Evaluate a batch of tool calls.

        Returns a list of ``(tool_name, action)`` tuples.
        """
        return [(name, self.evaluate(name, args)) for name, args in tool_calls]

    def is_auto_approved(self, tool_name: str, arguments: dict[str, Any] | None = None) -> bool:
        """Convenience: return *True* if the tool call is auto-approved."""
        action = self.evaluate(tool_name, arguments)
        return action == RuleAction.APPROVE

    def is_denied(self, tool_name: str, arguments: dict[str, Any] | None = None) -> bool:
        action = self.evaluate(tool_name, arguments)
        return action == RuleAction.DENY

    # -- Callbacks ----------------------------------------------------------

    def on_rule_match(self, callback: RuleMatchCallback) -> None:
        """Register a callback invoked whenever a rule matches."""
        self._match_callbacks.append(callback)

    def _fire_match_callbacks(self, rule: BatchRule, tool_name: str, arguments: dict[str, Any]) -> None:
        for cb in self._match_callbacks:
            try:
                cb(rule, tool_name, arguments)
            except Exception:
                logger.exception("Error in rule-match callback %s", cb)

    # -- Stats / diagnostics ------------------------------------------------

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def reset_stats(self) -> None:
        self._stats = {"total_evaluations": 0, "approved": 0, "denied": 0, "ask": 0, "no_match": 0}

    def rule_hit_report(self) -> list[dict[str, Any]]:
        """Return a sorted list of rules with their hit counts."""
        return sorted(
            [
                {"name": r.name, "action": r.action.value, "hits": r.hit_count, "enabled": r.enabled}
                for r in self._rules
            ],
            key=lambda x: x["hits"],
            reverse=True,
        )

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Snapshot the rule engine state."""
        return {
            "rules": [
                {
                    "name": r.name,
                    "tool_pattern": r.tool_pattern,
                    "command_pattern": r.command_pattern,
                    "path_pattern": r.path_pattern,
                    "action": r.action.value,
                    "scope": r.scope.value,
                    "priority": r.priority,
                    "enabled": r.enabled,
                    "description": r.description,
                    "hit_count": r.hit_count,
                }
                for r in self._rules
            ],
            "stats": self._stats,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutoApproveRules:
        """Reconstruct from a serialised dict."""
        rules = [
            BatchRule(
                name=rd["name"],
                tool_pattern=rd.get("tool_pattern", "*"),
                command_pattern=rd.get("command_pattern"),
                path_pattern=rd.get("path_pattern"),
                action=RuleAction(rd.get("action", "approve")),
                scope=RuleScope(rd.get("scope", "global")),
                priority=rd.get("priority", 0),
                enabled=rd.get("enabled", True),
                description=rd.get("description", ""),
                hit_count=rd.get("hit_count", 0),
            )
            for rd in data.get("rules", [])
        ]
        return cls(rules=rules)

    # -- Internals ----------------------------------------------------------

    def _sort_rules(self) -> None:
        """Sort rules by priority descending (stable sort preserves insertion order for ties)."""
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def __repr__(self) -> str:
        return f"AutoApproveRules(rules={len(self._rules)}, evaluated={self._stats.get('total_evaluations', 0)})"
