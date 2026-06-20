"""Final-readiness gate before the model may stop with a final answer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from likecodex_engine.agent.evidence import EvidenceLedger


@dataclass
class ReadinessResult:
    blocked: bool
    reason: str = ""
    incomplete_todos: int = 0
    missing_checks: int = 0


def final_readiness_check(
    ledger: EvidenceLedger,
    *,
    plan_mode_active: bool = False,
    project_checks: list[dict[str, Any]] | None = None,
    external_todos: list[dict[str, Any]] | None = None,
) -> ReadinessResult:
    """Return blocked=True when the agent must not emit a final answer yet."""
    if plan_mode_active:
        return ReadinessResult(blocked=False)

    missing_parts: list[str] = []
    incomplete = ledger.incomplete_todos()
    if not incomplete and external_todos:
        incomplete = [t for t in external_todos if str(t.get("status", "")).lower() not in {"completed", "cancelled"}]
    if incomplete:
        labels = ", ".join(str(t.get("content", t.get("id", "?"))) for t in incomplete[:5])
        missing_parts.append(f"incomplete todos: {labels}")

    writer_idx, has_writer = ledger.latest_successful_writer_index()
    checks = project_checks or []
    missing_checks = 0
    if has_writer and checks:
        for check in checks:
            command = str(check.get("command", "")).strip()
            if command and not ledger.has_successful_command_after(command, writer_idx):
                missing_checks += 1
                missing_parts.append(f"missing verification command: {command!r}")

    if not missing_parts:
        return ReadinessResult(blocked=False)

    return ReadinessResult(
        blocked=True,
        reason="; ".join(missing_parts),
        incomplete_todos=len(incomplete),
        missing_checks=missing_checks,
    )
