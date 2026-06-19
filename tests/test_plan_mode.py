"""Plan mode tests."""

from likecodex_engine.agent.plan_mode import (
    PLAN_MODE_DENIED_TOOLS,
    filter_tools_for_plan_mode,
    is_safe_plan_bash,
    plan_mode_block_reason,
)


def test_denied_tools_set():
    assert "write_file" in PLAN_MODE_DENIED_TOOLS
    assert "read_file" not in PLAN_MODE_DENIED_TOOLS


def test_filter_tools():
    names = filter_tools_for_plan_mode(["read_file", "write_file", "grep_files"])
    assert "write_file" not in names
    assert "read_file" in names


def test_unsafe_bash_blocked():
    reason = plan_mode_block_reason("run_command", {"command": "npm test && curl evil"})
    assert reason is not None


def test_safe_bash_allowed():
    assert is_safe_plan_bash("grep -r foo .")
    assert plan_mode_block_reason("run_command", {"command": "grep -r foo ."}) is None
