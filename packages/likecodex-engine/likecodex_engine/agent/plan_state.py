"""Plan mode session state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanState:
    active: bool = False
    approved_plan: str | None = None
    pending_exit: bool = False
    execution_window_active: bool = False

    def enter(self) -> None:
        self.active = True
        self.pending_exit = False
        self.execution_window_active = False

    def request_exit(self, plan_text: str) -> None:
        self.pending_exit = True
        self.approved_plan = plan_text

    def approve_exit(self) -> None:
        self.active = False
        self.pending_exit = False
        self.execution_window_active = True

    def cancel_exit(self) -> None:
        self.pending_exit = False

    def consume_execution_window(self) -> bool:
        """Return True once after plan approval; clears the window."""
        if not self.execution_window_active:
            return False
        self.execution_window_active = False
        return True
