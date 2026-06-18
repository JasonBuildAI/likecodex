"""Permission / approval evaluation for tool invocations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from likecodex_engine.permissions.classifier import RiskClassifier, RiskLevel


class ApprovalMode(StrEnum):
    READ_ONLY = "read-only"
    AUTO = "auto"
    FULL_ACCESS = "full-access"
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


class PermissionEvaluator:
    """Decides whether and where a tool call may execute."""

    def __init__(self, mode: ApprovalMode | str = ApprovalMode.AUTO) -> None:
        self.mode = ApprovalMode(mode)

    def evaluate(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        risk = RiskClassifier.classify_tool_call(tool_name, arguments)

        if self.mode == ApprovalMode.READ_ONLY:
            if risk == RiskLevel.LOW and tool_name in RiskClassifier.READ_ONLY_TOOLS:
                return PermissionDecision(True, ExecutionMode.LOCAL, "read-only mode allows reads")
            return PermissionDecision(False, ExecutionMode.DENY, "read-only mode denies writes")

        if self.mode == ApprovalMode.FULL_ACCESS:
            return PermissionDecision(True, ExecutionMode.LOCAL, "full-access mode allows all locally")

        if self.mode == ApprovalMode.SANDBOX_REQUIRED:
            if risk == RiskLevel.LOW and tool_name in RiskClassifier.READ_ONLY_TOOLS:
                return PermissionDecision(True, ExecutionMode.LOCAL, "reads allowed locally")
            return PermissionDecision(True, ExecutionMode.SANDBOX, "non-reads routed to sandbox")

        # AUTO mode
        if risk == RiskLevel.HIGH:
            return PermissionDecision(True, ExecutionMode.SANDBOX, "high-risk routed to sandbox")
        if risk == RiskLevel.MEDIUM:
            return PermissionDecision(True, ExecutionMode.PROMPT, "medium-risk requires approval")
        return PermissionDecision(True, ExecutionMode.LOCAL, "low-risk allowed locally")
