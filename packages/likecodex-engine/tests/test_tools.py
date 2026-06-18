"""Tests for individual tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from likecodex_engine.tools.filesystem import FileSystemTools
from likecodex_engine.tools.shell import ShellTools


@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path: Path) -> None:
    fs = FileSystemTools(str(tmp_path))
    result = await fs.write_file("test.txt", "hello")
    data = json.loads(result)
    assert data["written"] is True

    result = await fs.read_file("test.txt")
    data = json.loads(result)
    assert data["content"] == "hello"


@pytest.mark.asyncio
async def test_run_command(tmp_path: Path) -> None:
    shell = ShellTools(str(tmp_path))
    command = "echo ok" if sys.platform == "win32" else "echo ok"
    result = await shell.run_command(command)
    data = json.loads(result)
    assert "error" not in data
    assert data.get("exit_code") == 0
    assert "ok" in data.get("stdout", "")


@pytest.mark.asyncio
async def test_list_dir(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b").mkdir()
    fs = FileSystemTools(str(tmp_path))
    result = await fs.list_dir()
    data = json.loads(result)
    names = {e["name"] for e in data["entries"]}
    assert "a.txt" in names
    assert "b" in names
