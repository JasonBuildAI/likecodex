"""Permission / approval evaluation for tool invocations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from likecodex_engine.permissions.classifier import RiskClassifier, RiskLevel
from likecodex_engine.permissions.policy import Decision, Policy


class ApprovalMode(StrEnum):
    READ_ONLY = "read-only"
    ASK = "ask"  # Reasonix-compatible alias for auto-with-prompts
    AUTO = "auto"
    AUTO_APPROVE = "auto-approve"
    FULL_ACCESS = "full-access"
    YOLO = "yolo"
    SANDBOX_REQUIRED = "sandbox-required"


class ExecutionMode(StrEnum):
    LOCAL = "local"
    SANDBOX = "sandbox"
    DENY = "deny"
    PROMPT = "prompt"


@dataclass
class PermissionDecision:
    allowed: bool
    execution_mode: ExecutionMode
    reason: str


MEMORY_TOOLS = frozenset({"remember", "forget"})


class PermissionEvaluator:
    """Decides whether and where a tool call may execute."""

    def __init__(
        self,
        mode: ApprovalMode | str = ApprovalMode.AUTO,
        policy: Policy | None = None,
        working_dir: str = ".",
    ) -> None:
        self.mode = ApprovalMode(mode)
        self.policy = policy or Policy()
        self.grants_path = Path(working_dir) / ".likecodex" / "approvals.json"
        self.policy.load_grants(self.grants_path)

    def evaluate(self, tool_name: str, arguments: dict[str, Any], *, plan_execution_window: bool = False) -> PermissionDecision:
        read_only = tool_name in RiskClassifier.READ_ONLY_TOOLS or tool_name.startswith("lsp_")
        read_only = read_only or tool_name in {"history", "memory_search", "memory", "code_index", "ask"}

        if tool_name in MEMORY_TOOLS:
            return PermissionDecision(True, ExecutionMode.PROMPT, "memory tools always require approval")

        if plan_execution_window and tool_name not in MEMORY_TOOLS and tool_name != "ask":
            policy_decision = self.policy.decide(tool_name, read_only, arguments)
            if policy_decision != Decision.DENY:
                return PermissionDecision(True, ExecutionMode.LOCAL, "approved-plan execution window")

        policy_decision = self.policy.decide(tool_name, read_only, arguments)
        if policy_decision == Decision.DENY:
            return PermissionDecision(False, ExecutionMode.DENY, "Denied by policy rule")

        if self.mode == ApprovalMode.READ_ONLY:
            if read_only:
                return PermissionDecision(True, ExecutionMode.LOCAL, "read-only mode allows reads")
            return PermissionDecision(False, ExecutionMode.DENY, "read-only mode denies writes")

        if self.mode in (ApprovalMode.FULL_ACCESS, ApprovalMode.YOLO):
            if tool_name == "ask":
                return PermissionDecision(True, ExecutionMode.PROMPT, "ask requires user input")
            return PermissionDecision(True, ExecutionMode.LOCAL, f"{self.mode} allows all locally")

        if self.mode == ApprovalMode.AUTO_APPROVE:
            if read_only:
                return PermissionDecision(True, ExecutionMode.LOCAL, "reads allowed")
            if policy_decision == Decision.ASK:
                return PermissionDecision(True, ExecutionMode.PROMPT, "policy requires approval")
            return PermissionDecision(True, ExecutionMode.LOCAL, "auto-approve writer fallback")

        if self.mode == ApprovalMode.SANDBOX_REQUIRED:
            if read_only:
                return PermissionDecision(True, ExecutionMode.LOCAL, "reads allowed locally")
            return PermissionDecision(True, ExecutionMode.SANDBOX, "non-reads routed to sandbox")

        if self.mode in (ApprovalMode.AUTO, ApprovalMode.ASK):
            if policy_decision == Decision.ASK:
                return PermissionDecision(True, ExecutionMode.PROMPT, "policy requires approval")
            risk = RiskClassifier.classify_tool_call(tool_name, arguments)
            if risk == RiskLevel.HIGH:
                return PermissionDecision(True, ExecutionMode.SANDBOX, "high-risk routed to sandbox")
            if risk == RiskLevel.MEDIUM:
                return PermissionDecision(True, ExecutionMode.PROMPT, "medium-risk requires approval")
            return PermissionDecision(True, ExecutionMode.LOCAL, "low-risk allowed locally")

        return PermissionDecision(True, ExecutionMode.PROMPT, "policy requires approval")

    def grant_session(self, tool_name: str, arguments: dict[str, Any], scope: str = "once") -> None:
        from likecodex_engine.permissions.policy import extract_subject

        self.policy.grant_session(tool_name, extract_subject(tool_name, arguments), scope=scope)
        self.policy.save_grants(self.grants_path)
