"""Tests for the Phase 1 tool additions (encoding, fs, edit, todo, notebook, bgjobs)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from likecodex_engine.tools.edit_file import EditFileTools
from likecodex_engine.tools.encoding import decode_bytes, detect_encoding
from likecodex_engine.tools.filesystem import FileSystemTools
from likecodex_engine.tools.notebook import NotebookTools
from likecodex_engine.tools.shell import ShellTools
from likecodex_engine.tools.todo import TodoTools


def test_detect_encoding_utf8() -> None:
    assert detect_encoding("héllo".encode()) == "utf-8"


def test_detect_encoding_gbk() -> None:
    raw = "你好，世界".encode("gb18030")
    assert detect_encoding(raw) in ("gb18030", "gbk")
    assert decode_bytes(raw).text == "你好，世界"


def test_detect_encoding_utf16_bom() -> None:
    raw = "data".encode("utf-16")  # includes BOM
    enc = detect_encoding(raw)
    assert enc.startswith("utf-16")


@pytest.mark.asyncio
async def test_read_preserves_gbk_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "cn.txt"
    target.write_bytes("第一行\n第二行\n".encode("gb18030"))
    fs = FileSystemTools(str(tmp_path))

    read = json.loads(await fs.read_file("cn.txt"))
    assert "第一行" in read["content"]
    assert read["encoding"] in ("gb18030", "gbk")

    # Overwrite should keep the original (GBK-family) encoding.
    await fs.write_file("cn.txt", "第一行\n改过了\n")
    raw = target.read_bytes()
    assert raw.decode("gb18030") == "第一行\n改过了\n"


@pytest.mark.asyncio
async def test_glob_and_ls(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    (tmp_path / "src" / "b.py").write_text("y")
    (tmp_path / "readme.md").write_text("z")
    fs = FileSystemTools(str(tmp_path))

    g = json.loads(await fs.glob("**/*.py"))
    paths = {m["path"].replace("\\", "/") for m in g["matches"]}
    assert "src/a.py" in paths and "src/b.py" in paths
    assert g["count"] == 2

    listing = json.loads(await fs.ls("src"))
    names = {e["name"] for e in listing["entries"]}
    assert names == {"a.py", "b.py"}


@pytest.mark.asyncio
async def test_move_file(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_text("data")
    fs = FileSystemTools(str(tmp_path))
    res = json.loads(await fs.move_file("old.txt", "sub/new.txt"))
    assert res["moved"] is True
    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "sub" / "new.txt").read_text() == "data"


@pytest.mark.asyncio
async def test_multi_edit_atomic(tmp_path: Path) -> None:
    target = tmp_path / "code.py"
    target.write_text("a = 1\nb = 2\nc = 3\n")
    edit = EditFileTools(str(tmp_path))
    res = json.loads(
        await edit.multi_edit(
            "code.py",
            [
                {"old_string": "a = 1", "new_string": "a = 10"},
                {"old_string": "c = 3", "new_string": "c = 30"},
            ],
        )
    )
    assert res["edits_applied"] == 2
    assert target.read_text() == "a = 10\nb = 2\nc = 30\n"


@pytest.mark.asyncio
async def test_multi_edit_rolls_back_on_missing(tmp_path: Path) -> None:
    target = tmp_path / "code.py"
    target.write_text("a = 1\n")
    edit = EditFileTools(str(tmp_path))
    res = json.loads(
        await edit.multi_edit(
            "code.py",
            [{"old_string": "missing", "new_string": "x"}],
        )
    )
    assert "error" in res
    assert target.read_text() == "a = 1\n"  # unchanged


@pytest.mark.asyncio
async def test_delete_range(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("l1\nl2\nl3\nl4\n")
    edit = EditFileTools(str(tmp_path))
    res = json.loads(await edit.delete_range("f.txt", 2, 3))
    assert res["deleted_lines"] == 2
    assert target.read_text() == "l1\nl4\n"


@pytest.mark.asyncio
async def test_delete_symbol_python(tmp_path: Path) -> None:
    target = tmp_path / "m.py"
    target.write_text("def keep():\n    return 1\n\ndef drop():\n    return 2\n\nx = 3\n")
    edit = EditFileTools(str(tmp_path))
    res = json.loads(await edit.delete_symbol("m.py", "drop"))
    assert "error" not in res
    text = target.read_text()
    assert "def drop" not in text
    assert "def keep" in text
    assert "x = 3" in text


@pytest.mark.asyncio
async def test_todo_write() -> None:
    todo = TodoTools()
    res = json.loads(
        await todo.todo_write(
            [
                {"id": "1", "content": "first", "status": "completed"},
                {"id": "2", "content": "second", "status": "in_progress"},
            ]
        )
    )
    assert res["summary"]["completed"] == 1
    assert res["summary"]["in_progress"] == 1
    assert len(todo.current()) == 2


@pytest.mark.asyncio
async def test_notebook_edit(tmp_path: Path) -> None:
    code_cell = {
        "cell_type": "code",
        "metadata": {},
        "source": ["print(1)"],
        "outputs": [],
        "execution_count": None,
    }
    nb = {
        "cells": [code_cell],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    target = tmp_path / "nb.ipynb"
    target.write_text(json.dumps(nb), encoding="utf-8")
    tools = NotebookTools(str(tmp_path))

    res = json.loads(await tools.notebook_edit("nb.ipynb", 0, mode="replace", source="print(2)"))
    assert "error" not in res
    updated = json.loads(target.read_text(encoding="utf-8"))
    assert "print(2)" in "".join(updated["cells"][0]["source"])

    res = json.loads(await tools.notebook_edit("nb.ipynb", 1, mode="insert", source="x = 5", cell_type="code"))
    assert res["cells"] == 2


@pytest.mark.asyncio
async def test_bgjobs_lifecycle(tmp_path: Path) -> None:
    shell = ShellTools(str(tmp_path))
    started = json.loads(await shell.bgjobs("start", command="echo hi"))
    job_id = started["job_id"]
    assert started["running"] is True

    # Give the background drain a moment to finish.
    for _ in range(50):
        status = json.loads(await shell.bgjobs("status", job_id=job_id))
        if not status["running"]:
            break
        await asyncio.sleep(0.1)
    assert "hi" in status["stdout"]

    listing = json.loads(await shell.bgjobs("list"))
    assert any(j["job_id"] == job_id for j in listing["jobs"])
