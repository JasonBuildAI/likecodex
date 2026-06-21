"""Entrypoint parity: /chat, /run, /tasks share expand_prompt + plan mode."""

from __future__ import annotations

import pytest

from likecodex_engine.agent.commands import expand_prompt
from likecodex_engine.agent.plan_state import PlanState
from likecodex_engine.server_turn import apply_plan_state


class _Runner:
    def __init__(self) -> None:
        self.plan_state = PlanState()
        self.goal_state = __import__(
            "likecodex_engine.agent.goal", fromlist=["GoalState"]
        ).GoalState()


def test_plan_slash_expansion():
    expanded = expand_prompt("/plan", ".")
    assert expanded.plan_mode_enter is True
    runner = _Runner()
    events = apply_plan_state(expanded, runner, ".")
    assert runner.plan_state.active is True
    assert any(e.event_type == "plan_mode_changed" for e in events)


def test_exit_plan_approve_sets_execution_window():
    expanded = expand_prompt("/exit_plan approve", ".")
    runner = _Runner()
    apply_plan_state(expanded, runner, ".")
    assert runner.plan_state.active is False
    assert runner.plan_state.execution_window_active is True


def test_goal_start():
    expanded = expand_prompt("/goal --research fix flaky tests", ".")
    assert expanded.goal_start is not None
    runner = _Runner()
    apply_plan_state(expanded, runner, ".")
    assert runner.goal_state.active is True
    assert runner.goal_state.strategy == "research"
