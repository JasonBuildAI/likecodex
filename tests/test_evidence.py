"""Evidence ledger tests."""

from likecodex_engine.agent.evidence import EvidenceLedger, command_matches


def test_command_matches_prefix():
    assert command_matches("go test ./...", "go test ./... -count=1")
    assert command_matches("pytest", "pytest tests/test_x.py")


def test_has_successful_command():
    ledger = EvidenceLedger()
    ledger.record("run_command", {"command": "pytest tests/"}, success=True)
    assert ledger.has_successful_command("pytest tests/")


def test_complete_step_receipt():
    ledger = EvidenceLedger()
    ledger.record(
        "complete_step",
        {"step": "Add parser", "result": "done", "evidence": []},
        success=True,
        step="Add parser",
    )
    assert ledger.has_successful_complete_step("Add parser")


def test_newly_completed_without_receipt():
    ledger = EvidenceLedger()
    previous = [{"id": "1", "content": "Add parser", "status": "in_progress"}]
    updated = [{"id": "1", "content": "Add parser", "status": "completed"}]
    missing = ledger.newly_completed_without_receipt(previous, updated)
    assert len(missing) == 1
