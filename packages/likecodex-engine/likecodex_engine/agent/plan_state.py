"""Plan mode session state with status mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlanStatus(str, Enum):
    """Plan lifecycle status mapping."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PENDING_EXIT = "pending_exit"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class PlanState:
    active: bool = False
    approved_plan: str | None = None
    pending_exit: bool = False
    execution_window_active: bool = False
    plan_steps: list[dict[str, Any]] = field(default_factory=list)
    current_step_index: int = -1
    status: PlanStatus = PlanStatus.INACTIVE

    def enter(self) -> None:
        self.active = True
        self.pending_exit = False
        self.execution_window_active = False
        self.status = PlanStatus.ACTIVE

    def request_exit(self, plan_text: str) -> None:
        self.pending_exit = True
        self.approved_plan = plan_text
        self.status = PlanStatus.PENDING_EXIT

    def approve_exit(self) -> None:
        self.active = False
        self.pending_exit = False
        self.execution_window_active = True
        self.status = PlanStatus.EXECUTING

    def cancel_exit(self) -> None:
        self.pending_exit = False
        self.status = PlanStatus.ACTIVE

    def consume_execution_window(self) -> bool:
        """Return True once after plan approval; clears the window."""
        if not self.execution_window_active:
            return False
        self.execution_window_active = False
        self.status = PlanStatus.INACTIVE
        return True

    def complete(self) -> None:
        """Mark plan as completed."""
        self.status = PlanStatus.COMPLETED
        self.active = False

    def cancel(self) -> None:
        """Cancel the current plan."""
        self.status = PlanStatus.CANCELLED
        self.active = False
        self.pending_exit = False
        self.execution_window_active = False

    def set_steps(self, steps: list[dict[str, Any]]) -> None:
        """Set plan steps."""
        self.plan_steps = steps
        self.current_step_index = -1

    def next_step(self) -> dict[str, Any] | None:
        """Advance to next plan step."""
        self.current_step_index += 1
        if self.current_step_index >= len(self.plan_steps):
            return None
        return self.plan_steps[self.current_step_index]

    def can_execute_tool(self, is_write: bool = False) -> bool:
        """Check if tool execution is allowed in current state."""
        if self.status == PlanStatus.INACTIVE:
            return True
        if self.status == PlanStatus.EXECUTING:
            return True
        if self.status == PlanStatus.ACTIVE:
            return not is_write  # read-only allowed in active plan mode
        return False
