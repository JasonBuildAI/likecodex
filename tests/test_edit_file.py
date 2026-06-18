"""Tests for edit_file SEARCH/REPLACE tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from likecodex_engine.tools.edit_file import EditFileTools


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    target = tmp_path / "sample.py"
    target.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    return tmp_path


@pytest.mark.asyncio
async def test_edit_file_exact_replace(workspace: Path) -> None:
    tools = EditFileTools(str(workspace))
    raw = await tools.edit_file("sample.py", "return 'world'", "return 'likecodex'")
    data = json.loads(raw)
    assert data["replacements"] == 1
    assert "likecodex" in (workspace / "sample.py").read_text(encoding="utf-8")
    assert "diff" in data


@pytest.mark.asyncio
async def test_edit_file_not_found(workspace: Path) -> None:
    tools = EditFileTools(str(workspace))
    raw = await tools.edit_file("sample.py", "missing needle", "x")
    data = json.loads(raw)
    assert "error" in data
    assert "hint" in data


@pytest.mark.asyncio
async def test_edit_file_rejects_escape(workspace: Path) -> None:
    tools = EditFileTools(str(workspace))
    raw = await tools.edit_file("../../etc/passwd", "x", "y")
    data = json.loads(raw)
    assert "error" in data
