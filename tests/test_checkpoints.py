"""Checkpoint and complete_step tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from likecodex_engine.agent.checkpoints import CheckpointManager
from likecodex_engine.tools.plan_progress import PlanProgressTools


def test_snapshot_and_rewind(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("v1", encoding="utf-8")
    mgr = CheckpointManager(str(tmp_path))
    cp = mgr.snapshot(["a.txt"], label="write_file")
    assert cp is not None
    target.write_text("v2", encoding="utf-8")
    result = mgr.rewind(cp.id)
    assert result.get("rewound") is True
    assert target.read_text(encoding="utf-8") == "v1"


def test_snapshot_ignores_escape(tmp_path: Path) -> None:
    mgr = CheckpointManager(tmp_path)
    cp = mgr.snapshot(["../outside.txt"], label="edit_file")
    assert cp is not None
    assert cp.files == []


@pytest.mark.asyncio
async def test_complete_step_requires_evidence() -> None:
    tools = PlanProgressTools()
    res = json.loads(await tools.complete_step("1", "done", []))
    assert res["accepted"] is False

    res = json.loads(await tools.complete_step("1", "done", [{"kind": "bogus", "summary": "x"}]))
    assert res["accepted"] is False


@pytest.mark.asyncio
async def test_complete_step_records() -> None:
    tools = PlanProgressTools()
    res = json.loads(
        await tools.complete_step(
            "1",
            "added function",
            [{"kind": "manual", "summary": "3 passed"}],
        )
    )
    assert res["accepted"] is True
    assert len(tools.completed()) == 1
