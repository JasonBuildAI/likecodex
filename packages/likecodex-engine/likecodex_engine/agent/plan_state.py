"""Plan mode session state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanState:
    active: bool = False
    approved_plan: str | None = None
    pending_exit: bool = False

    def enter(self) -> None:
        self.active = True
        self.pending_exit = False

    def request_exit(self, plan_text: str) -> None:
        self.pending_exit = True
        self.approved_plan = plan_text

    def approve_exit(self) -> None:
        self.active = False
        self.pending_exit = False

    def cancel_exit(self) -> None:
        self.pending_exit = False
