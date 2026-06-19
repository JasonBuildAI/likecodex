"""Plan state machine tests."""

from likecodex_engine.agent.commands import expand_prompt
from likecodex_engine.agent.plan_state import PlanState


def test_plan_state_enter_and_pending_exit():
    state = PlanState()
    state.enter()
    assert state.active
    state.request_exit("Plan summary here")
    assert state.pending_exit
    assert state.approved_plan == "Plan summary here"
    assert state.active
    state.approve_exit()
    assert not state.active
    assert not state.pending_exit


def test_exit_plan_requires_approval(tmp_path):
    expanded = expand_prompt("/exit_plan", tmp_path)
    assert expanded.plan_mode_exit_request
    assert expanded.direct_reply is not None

    approve = expand_prompt("/exit_plan approve", tmp_path)
    assert approve.plan_mode_exit_approve
