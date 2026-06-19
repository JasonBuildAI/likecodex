"""Cross-turn batch storm breaker tests (Reasonix applyStormBreaker parity)."""

from likecodex_engine.agent.guards import (
    LOOP_GUARD_PREFIX,
    STORM_BREAK_THRESHOLD,
    StormBreaker,
    ToolTurnOutcome,
    batch_storm_signature,
)


def _fail(name: str, err: str = "unexpected end of JSON input") -> ToolTurnOutcome:
    return ToolTurnOutcome(
        tool_call_id=f"id-{name}",
        tool_name=name,
        output=f'{{"error": "{err}"}}',
        error_msg=err,
    )


def _ok(name: str) -> ToolTurnOutcome:
    return ToolTurnOutcome(
        tool_call_id=f"id-{name}",
        tool_name=name,
        output="ok",
        error_msg="",
    )


def test_batch_storm_signature_requires_all_errors() -> None:
    sig, ok = batch_storm_signature([_fail("write_file"), _ok("read_file")])
    assert not ok
    assert sig == ""


def test_storm_breaker_escalates_repeated_failure() -> None:
    breaker = StormBreaker()
    notices: list[str] = []
    last_output = ""
    for i in range(STORM_BREAK_THRESHOLD):
        outcomes = [_fail("write_file")]
        outcomes[0].tool_call_id = f"id-{i}"
        storm = breaker.apply_turn(outcomes)
        if storm is not None:
            _, last_output, notice = storm
            notices.append(notice)

    assert LOOP_GUARD_PREFIX in last_output
    assert "write_file" in last_output
    assert "unexpected end of JSON input" in last_output
    assert notices


def test_storm_breaker_escalates_repeated_batch() -> None:
    breaker = StormBreaker()
    batch = [_fail("write_a"), _fail("write_b")]
    storm = None
    for _ in range(STORM_BREAK_THRESHOLD):
        storm = breaker.apply_turn(batch)
    assert storm is not None
    _, output, notice = storm
    assert LOOP_GUARD_PREFIX in output
    assert "batch of 2" in output
    assert "loop guard" in notice


def test_storm_breaker_silent_below_threshold() -> None:
    breaker = StormBreaker()
    for _ in range(STORM_BREAK_THRESHOLD - 1):
        assert breaker.apply_turn([_fail("write_file")]) is None


def test_storm_breaker_resets_on_success() -> None:
    breaker = StormBreaker()
    fail = [_fail("write_file")]
    good = [_ok("read_file")]

    breaker.apply_turn(fail)
    breaker.apply_turn(fail)
    breaker.apply_turn(good)
    breaker.apply_turn(fail)
    assert breaker.apply_turn(fail) is None


def test_storm_breaker_batch_resets_on_partial_success() -> None:
    breaker = StormBreaker()
    batch = [_fail("write_file"), _ok("read_file")]
    for _ in range(STORM_BREAK_THRESHOLD + 2):
        assert breaker.apply_turn(batch) is None
