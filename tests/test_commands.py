"""Tests for slash commands, @-references, /init, and project memory."""

from __future__ import annotations

from pathlib import Path

from likecodex_engine.agent.commands import expand_prompt, generate_project_memory, load_slash_commands
from likecodex_engine.context.project_memory import discover_memory_files, load_project_memory


def test_load_slash_commands(tmp_path: Path) -> None:
    cmd_dir = tmp_path / ".likecodex" / "commands"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "review.md").write_text("Please review $ARGS carefully.", encoding="utf-8")
    commands = load_slash_commands(tmp_path)
    assert "review" in commands


def test_expand_slash_command_with_args(tmp_path: Path) -> None:
    cmd_dir = tmp_path / ".likecodex" / "commands"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "fix.md").write_text("Fix the bug in $1 then run tests. Details: $ARGS", encoding="utf-8")
    result = expand_prompt("/fix auth.py urgent", tmp_path)
    assert "auth.py" in result.prompt
    assert "auth.py urgent" in result.prompt
    assert result.direct_reply is None


def test_at_reference_injects_file(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("important content", encoding="utf-8")
    result = expand_prompt("look at @notes.txt please", tmp_path)
    assert any("important content" in block for block in result.context_blocks)


def test_at_reference_directory(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x", encoding="utf-8")
    result = expand_prompt("check @src", tmp_path)
    assert any("a.py" in block for block in result.context_blocks)


def test_at_reference_blocks_escape(tmp_path: Path) -> None:
    result = expand_prompt("read @../secret.txt", tmp_path)
    assert result.context_blocks == []


def test_compact_command_sets_trigger() -> None:
    result = expand_prompt("/compact keep auth decisions", ".")
    assert result.compact_trigger is True
    assert result.compact_focus == "keep auth decisions"
    assert result.direct_reply is None


def test_compact_command_without_focus() -> None:
    result = expand_prompt("/compact", ".")
    assert result.compact_trigger is True
    assert result.compact_focus == ""


def test_init_generates_memory(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)", encoding="utf-8")
    result = expand_prompt("/init", tmp_path)
    assert result.direct_reply is not None
    assert (tmp_path / "LIKECODEX.md").exists()


def test_generate_project_memory_contents(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# hi", encoding="utf-8")
    path = generate_project_memory(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "Project Memory" in text
    assert "`.py`" in text


def test_discover_and_load_project_memory(tmp_path: Path) -> None:
    (tmp_path / "LIKECODEX.md").write_text("Use tabs not spaces.", encoding="utf-8")
    files = discover_memory_files(tmp_path)
    assert any(f.name == "LIKECODEX.md" for f in files)
    assert "tabs" in load_project_memory(tmp_path)
