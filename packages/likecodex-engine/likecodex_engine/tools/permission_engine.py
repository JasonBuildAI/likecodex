"""High-level permission decision engine for tool invocations.

Sits on top of the existing ``permissions.policy`` / ``permissions.evaluator``
layer and adds Agent-mode-aware decisions, tool metadata tracking, and
session-level grant management.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from likecodex_engine.agent.mode_manager import (
    AgentMode,
    ModeManager,
    PermissionLevel,
)
from likecodex_engine.permissions.evaluator import (
    ApprovalMode,
    ExecutionMode,
    PermissionDecision,
    PermissionEvaluator,
)
from likecodex_engine.permissions.policy import Decision, Policy, extract_subject

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool metadata
# ---------------------------------------------------------------------------

class ToolRisk(StrEnum):
    """Intrinsic risk tier of a tool (independent of mode)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolCategory(StrEnum):
    """Broad functional category for grouping tools."""
    READ = "read"
    WRITE = "write"
    SHELL = "shell"
    WEB = "web"
    GIT = "git"
    MEMORY = "memory"
    LSP = "lsp"
    META = "meta"


@dataclass(frozen=True)
class ToolMetadata:
    """Static metadata describing a single tool's permission profile."""
    name: str
    category: ToolCategory
    risk: ToolRisk
    read_only: bool = True
    description: str = ""

    # Default per-mode behaviour
    # When True the tool is auto-approved in Agent mode without user prompt.
    auto_in_agent: bool = True
    # When True the tool always requires explicit user confirmation.
    always_ask: bool = False


# Pre-built metadata registry for known tools.
_DEFAULT_TOOL_REGISTRY: dict[str, ToolMetadata] = {}


def _register_default_tools() -> None:
    """Populate the default tool registry. Called once at module import."""
    entries: list[ToolMetadata] = [
        # Read tools
        ToolMetadata("read_file", ToolCategory.READ, ToolRisk.LOW, read_only=True),
        ToolMetadata("list_dir", ToolCategory.READ, ToolRisk.LOW, read_only=True),
        ToolMetadata("ls", ToolCategory.READ, ToolRisk.LOW, read_only=True),
        ToolMetadata("glob", ToolCategory.READ, ToolRisk.LOW, read_only=True),
        ToolMetadata("search_files", ToolCategory.READ, ToolRisk.LOW, read_only=True),
        ToolMetadata("grep_files", ToolCategory.READ, ToolRisk.LOW, read_only=True),
        # Git read
        ToolMetadata("git_status", ToolCategory.GIT, ToolRisk.LOW, read_only=True),
        ToolMetadata("git_diff", ToolCategory.GIT, ToolRisk.LOW, read_only=True),
        ToolMetadata("git_log", ToolCategory.GIT, ToolRisk.LOW, read_only=True),
        ToolMetadata("git_branch", ToolCategory.GIT, ToolRisk.LOW, read_only=True),
        # Web
        ToolMetadata("web_fetch", ToolCategory.WEB, ToolRisk.MEDIUM, read_only=True),
        ToolMetadata("web_search", ToolCategory.WEB, ToolRisk.LOW, read_only=True),
        # Write tools
        ToolMetadata("write_file", ToolCategory.WRITE, ToolRisk.MEDIUM, read_only=False),
        ToolMetadata("edit_file", ToolCategory.WRITE, ToolRisk.MEDIUM, read_only=False),
        ToolMetadata("multi_edit", ToolCategory.WRITE, ToolRisk.MEDIUM, read_only=False),
        ToolMetadata("move_file", ToolCategory.WRITE, ToolRisk.MEDIUM, read_only=False),
        ToolMetadata("delete_range", ToolCategory.WRITE, ToolRisk.MEDIUM, read_only=False),
        ToolMetadata("delete_symbol", ToolCategory.WRITE, ToolRisk.MEDIUM, read_only=False),
        ToolMetadata("notebook_edit", ToolCategory.WRITE, ToolRisk.MEDIUM, read_only=False),
        # Shell
        ToolMetadata("run_command", ToolCategory.SHELL, ToolRisk.HIGH, read_only=False, auto_in_agent=False),
        # Git write
        ToolMetadata("git_commit", ToolCategory.GIT, ToolRisk.MEDIUM, read_only=False),
        # Memory
        ToolMetadata("remember", ToolCategory.MEMORY, ToolRisk.LOW, read_only=False, always_ask=True),
        ToolMetadata("forget", ToolCategory.MEMORY, ToolRisk.LOW, read_only=False, always_ask=True),
        # Meta
        ToolMetadata("ask", ToolCategory.META, ToolRisk.LOW, read_only=True, always_ask=True),
        ToolMetadata("history", ToolCategory.META, ToolRisk.LOW, read_only=True),
        ToolMetadata("memory_search", ToolCategory.MEMORY, ToolRisk.LOW, read_only=True),
        ToolMetadata("memory", ToolCategory.MEMORY, ToolRisk.LOW, read_only=True),
        ToolMetadata("code_index", ToolCategory.META, ToolRisk.LOW, read_only=True),
    ]
    for entry in entries:
        _DEFAULT_TOOL_REGISTRY[entry.name] = entry


_register_default_tools()


def get_tool_metadata(tool_name: str) -> ToolMetadata:
    """Return metadata for *tool_name*, creating a sensible default if unknown."""
    if tool_name in _DEFAULT_TOOL_REGISTRY:
        return _DEFAULT_TOOL_REGISTRY[tool_name]
    # LSP tools default to low-risk read
    if tool_name.startswith("lsp_"):
        return ToolMetadata(tool_name, ToolCategory.LSP, ToolRisk.LOW, read_only=True)
    # Unknown tools default to medium-risk write
    return ToolMetadata(tool_name, ToolCategory.META, ToolRisk.MEDIUM, read_only=False, auto_in_agent=False)


# ---------------------------------------------------------------------------
# PermissionDecision (extended)
# ---------------------------------------------------------------------------

@dataclass
class AgentPermissionResult:
    """Result of a permission check in the Agent-mode context."""
    allowed: bool
    requires_confirmation: bool
    execution_mode: ExecutionMode
    reason: str
    tool_metadata: ToolMetadata | None = None
    warnings: list[str] = field(default_factory=list)
    # Timestamp for auditing
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# PermissionEngine
# ---------------------------------------------------------------------------

class PermissionEngine:
    """Unified permission engine that combines:

    - :class:`ModeManager` — current interaction mode
    - :class:`PermissionEvaluator` — existing risk / policy evaluation
    - :class:`ToolMetadata` — static tool profiles

    This is the single entry-point the agent loop should call before
    executing any tool.
    """

    def __init__(
        self,
        mode_manager: ModeManager | None = None,
        policy: Policy | None = None,
        working_dir: str = ".",
    ) -> None:
        self.mode_manager = mode_manager or ModeManager()

        # Map AgentMode → ApprovalMode for the underlying evaluator
        approval_mode = self._agent_mode_to_approval(self.mode_manager.mode)
        self._evaluator = PermissionEvaluator(
            mode=approval_mode,
            policy=policy,
            working_dir=working_dir,
        )

        # Session-level grant cache: tool_name → set of subjects
        self._session_grants: dict[str, set[str]] = {}

        # Audit log
        self._audit_log: list[AgentPermissionResult] = []

    # -- Main entry point ---------------------------------------------------

    def check(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        plan_execution_window: bool = False,
    ) -> AgentPermissionResult:
        """Evaluate whether *tool_name* may execute with *arguments*.

        This is the primary method the agent loop calls before every tool
        invocation.
        """
        arguments = arguments or {}
        meta = get_tool_metadata(tool_name)

        # 1. Always-ask tools short-circuit everything
        if meta.always_ask:
            result = AgentPermissionResult(
                allowed=True,
                requires_confirmation=True,
                execution_mode=ExecutionMode.PROMPT,
                reason=f"{tool_name} always requires user confirmation",
                tool_metadata=meta,
            )
            self._audit(result)
            return result

        # 2. Check session grants
        subject = extract_subject(tool_name, arguments)
        if self._check_session_grant(tool_name, subject):
            result = AgentPermissionResult(
                allowed=True,
                requires_confirmation=False,
                execution_mode=ExecutionMode.LOCAL,
                reason="session grant",
                tool_metadata=meta,
            )
            self._audit(result)
            return result

        # 3. Delegate to the underlying evaluator
        inner: PermissionDecision = self._evaluator.evaluate(
            tool_name,
            arguments,
            plan_execution_window=plan_execution_window,
        )

        # 4. Apply Agent-mode overrides
        requires_confirmation = not inner.allowed or inner.execution_mode == ExecutionMode.PROMPT

        if self.mode_manager.mode == AgentMode.AGENT and meta.auto_in_agent:
            # In Agent mode, auto-approve unless the inner evaluator DENIED
            if inner.execution_mode != ExecutionMode.DENY:
                requires_confirmation = False

        if self.mode_manager.mode == AgentMode.ASK and not meta.read_only:
            # Ask mode blocks all writes
            result = AgentPermissionResult(
                allowed=False,
                requires_confirmation=False,
                execution_mode=ExecutionMode.DENY,
                reason="Ask mode denies write operations",
                tool_metadata=meta,
            )
            self._audit(result)
            return result

        result = AgentPermissionResult(
            allowed=inner.allowed,
            requires_confirmation=requires_confirmation,
            execution_mode=inner.execution_mode,
            reason=inner.reason,
            tool_metadata=meta,
            warnings=inner.warnings,
        )
        self._audit(result)
        return result

    # -- Session grants -----------------------------------------------------

    def grant(
        self,
        tool_name: str,
        subject: str | None = None,
        scope: str = "session",
    ) -> None:
        """Grant permission for *tool_name* (optionally scoped to *subject*).

        Parameters
        ----------
        scope:
            ``"once"`` — single use (not persisted)
            ``"session"`` — persists for the current session
            ``"always"`` — persists across sessions (saved to disk)
        """
        key = tool_name
        if key not in self._session_grants:
            self._session_grants[key] = set()

        if subject:
            self._session_grants[key].add(subject)
        else:
            self._session_grants[key].add("*")

        # Also propagate to the underlying evaluator's policy
        grant_subject = subject or extract_subject(tool_name, arguments={}) or None
        self._evaluator.grant_session(tool_name, grant_subject, scope=scope)
        logger.debug("Granted %s for %s (subject=%s)", scope, tool_name, grant_subject)

    def revoke(self, tool_name: str, subject: str | None = None) -> None:
        """Revoke a previously granted session permission."""
        if tool_name not in self._session_grants:
            return
        if subject:
            self._session_grants[tool_name].discard(subject)
        else:
            self._session_grants.pop(tool_name, None)

    def _check_session_grant(self, tool_name: str, subject: str | None) -> bool:
        if tool_name not in self._session_grants:
            return False
        grants = self._session_grants[tool_name]
        if "*" in grants:
            return True
        if subject and subject in grants:
            return True
        return False

    # -- Mode sync ----------------------------------------------------------

    def sync_mode(self) -> None:
        """Re-sync the underlying evaluator with the current AgentMode.

        Call this after a mode transition to keep the evaluator consistent.
        """
        approval = self._agent_mode_to_approval(self.mode_manager.mode)
        self._evaluator.mode = ApprovalMode(approval)
        logger.info("PermissionEngine synced to mode=%s approval=%s", self.mode_manager.mode.value, approval)

    # -- Audit log ----------------------------------------------------------

    @property
    def audit_log(self) -> list[AgentPermissionResult]:
        return list(self._audit_log)

    def _audit(self, result: AgentPermissionResult) -> None:
        self._audit_log.append(result)

    def clear_audit(self) -> None:
        self._audit_log.clear()

    # -- Internals ----------------------------------------------------------

    @staticmethod
    def _agent_mode_to_approval(mode: AgentMode | str) -> ApprovalMode:
        mapping: dict[str, ApprovalMode] = {
            AgentMode.ASK: ApprovalMode.READ_ONLY,
            AgentMode.AGENT: ApprovalMode.AUTO,
            AgentMode.MANUAL: ApprovalMode.ASK,
        }
        return mapping.get(str(mode), ApprovalMode.AUTO)

    # -- Convenience --------------------------------------------------------

    def batch_check(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
    ) -> list[AgentPermissionResult]:
        """Check a batch of tool calls and return results in order."""
        return [self.check(name, args) for name, args in tool_calls]

    def summary(self) -> dict[str, Any]:
        """Return a summary of the engine state for debugging / UI."""
        return {
            "mode": self.mode_manager.mode.value,
            "permission_level": self.mode_manager.permission_level.value,
            "session_grants": {k: sorted(v) for k, v in self._session_grants.items()},
            "audit_count": len(self._audit_log),
            "last_decision": (
                {
                    "tool": self._audit_log[-1].tool_metadata.name if self._audit_log[-1].tool_metadata else None,
                    "allowed": self._audit_log[-1].allowed,
                    "reason": self._audit_log[-1].reason,
                }
                if self._audit_log
                else None
            ),
        }

    def __repr__(self) -> str:
        return (
            f"PermissionEngine(mode={self.mode_manager.mode.value!r}, "
            f"grants={len(self._session_grants)}, "
            f"audit={len(self._audit_log)})"
        )
