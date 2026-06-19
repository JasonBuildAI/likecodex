"""Agent harness tests."""

import json

from likecodex_engine.agent.guards import LoopGuard
from likecodex_engine.agent.plan_mode import is_plan_mode_denied_tool, is_safe_plan_bash, plan_mode_block_reason


def test_loop_guard_trips_after_threshold():
    guard = LoopGuard(threshold=3)
    args = {"path": "x"}
    for _ in range(2):
        assert not guard.record_failure("read_file", args, "not found")
    assert guard.record_failure("read_file", args, "not found")
    msg = guard.guard_message("read_file", args, "not found")
    assert "[loop guard]" in msg


def test_loop_guard_resets_on_success():
    guard = LoopGuard(threshold=3)
    args = {"command": "ls"}
    guard.record_failure("run_command", args, "fail")
    guard.record_success("run_command", args)
    assert guard.record_failure("run_command", args, "fail") is False


def test_plan_mode_denies_write_tools():
    assert is_plan_mode_denied_tool("write_file")
    assert plan_mode_block_reason("edit_file", {"path": "a.py"}) is not None


def test_plan_mode_allows_safe_bash():
    assert is_safe_plan_bash("git status")
    assert not is_safe_plan_bash("git status && rm -rf /")


def test_loop_guard_detects_json_error():
    guard = LoopGuard()
    assert guard.is_error_result(json.dumps({"error": "nope"}))
