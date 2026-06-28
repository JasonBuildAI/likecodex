"""Goal mode: autonomous multi-turn continuation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


GOAL_MARKER = re.compile(r"\[goal:(continue|complete|blocked)\]", re.IGNORECASE)


@dataclass
class GoalState:
    objective: str = ""
    active: bool = False
    strategy: str = "simple"  # simple | research
    continuation_count: int = 0
    max_continuations: int = 20
    blocked_count: int = 0

    def start(self, objective: str, strategy: str = "simple") -> None:
        self.objective = objective.strip()
        self.active = bool(self.objective)
        self.strategy = strategy
        self.continuation_count = 0
        self.blocked_count = 0

    def clear(self) -> None:
        self.objective = ""
        self.active = False
        self.continuation_count = 0
        self.blocked_count = 0

    def transient_block(self) -> str:
        if not self.active:
            return ""
        strategy_note = ""
        if self.strategy == "research":
            strategy_note = (
                "\nAutoResearch: maintain hypotheses under .likecodex/autoresearch/, "
                "pivot when blocked twice."
            )
        return (
            f"[Active Goal]\nObjective: {self.objective}\n"
            f"Report progress with [goal:continue], [goal:complete], or [goal:blocked]."
            f"{strategy_note}"
        )

    def _handle_complete(self) -> str | None:
        self.clear()
        return None

    def _handle_blocked(self) -> str | None:
        self.blocked_count += 1
        if self.blocked_count >= 3:
            self.clear()
            return None
        return f"[goal:continue] Previous step blocked ({self.blocked_count}/3). Try another approach."

    def _handle_continue(self) -> str | None:
        self.blocked_count = 0
        self.continuation_count += 1
        if self.continuation_count >= self.max_continuations:
            self.clear()
            return None
        return f"[goal:continue] Continue working toward: {self.objective}"

    _ACTION_HANDLERS = {
        "complete": _handle_complete,
        "blocked": _handle_blocked,
        "continue": _handle_continue,
    }

    def parse_response(self, text: str) -> str | None:
        """Return follow-up user message if host should continue."""
        if not self.active:
            return None
        m = GOAL_MARKER.search(text)
        if not m:
            return None
        handler = self._ACTION_HANDLERS.get(m.group(1).lower())
        return handler(self) if handler else None
