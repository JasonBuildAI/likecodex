"""Repeat-success guard tests."""

from likecodex_engine.agent.guards import RepeatSuccessGuard


def test_blocks_after_threshold_writes():
    guard = RepeatSuccessGuard(threshold=3)
    args = {"path": "a.py", "content": "x"}
    assert guard.should_block("write_file", args) is None
    for _ in range(3):
        guard.record_success("write_file", args)
    msg = guard.should_block("write_file", args)
    assert msg is not None
    assert "[loop guard]" in msg
