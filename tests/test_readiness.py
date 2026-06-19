"""Final-readiness gate tests."""

from likecodex_engine.agent.evidence import EvidenceLedger
from likecodex_engine.agent.readiness import final_readiness_check


def test_blocks_incomplete_todos():
    ledger = EvidenceLedger()
    ledger.record(
        "todo_write",
        {"todos": [{"id": "1", "content": "Ship feature", "status": "in_progress"}]},
        success=True,
    )
    result = final_readiness_check(ledger)
    assert result.blocked
    assert "incomplete todos" in result.reason


def test_allows_when_no_todos():
    ledger = EvidenceLedger()
    result = final_readiness_check(ledger)
    assert not result.blocked


def test_skips_in_plan_mode():
    ledger = EvidenceLedger()
    ledger.record(
        "todo_write",
        {"todos": [{"id": "1", "content": "Ship feature", "status": "pending"}]},
        success=True,
    )
    result = final_readiness_check(ledger, plan_mode_active=True)
    assert not result.blocked
