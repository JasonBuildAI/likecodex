"""Tests for host checks extraction from project memory."""

from __future__ import annotations

from pathlib import Path

from likecodex_engine.context.instruction import (
    VerifyCheck,
    extract_host_checks,
    load_host_checks_from_dir,
)


def test_extract_host_checks_basic():
    """Test basic extraction of verify: bullets from host checks section."""
    docs = [
        (
            "LIKECODEX.md",
            """# Project Memory

## Overview

Some overview text.

## LikeCodex host checks

- verify: pytest
- verify: ruff check .
- verify: mypy src/

## Other section

This should not be parsed.
""",
        )
    ]

    checks = extract_host_checks(docs)

    assert len(checks) == 3
    assert checks[0].command == "pytest"
    assert checks[0].source_path == "LIKECODEX.md"
    assert checks[0].line == 9
    assert checks[1].command == "ruff check ."
    assert checks[2].command == "mypy src/"


def test_extract_host_checks_case_insensitive():
    """Test that section heading is case-insensitive."""
    docs = [
        (
            "AGENTS.md",
            """# Agents

## LIKECODEX HOST CHECKS

- verify: npm test

## Another section
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 1
    assert checks[0].command == "npm test"


def test_extract_host_checks_deduplication():
    """Test that duplicate commands are removed."""
    docs = [
        (
            "LIKECODEX.md",
            """## LikeCodex host checks

- verify: pytest
- verify: pytest
- verify: ruff check
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 2
    commands = [c.command for c in checks]
    assert "pytest" in commands
    assert "ruff check" in commands


def test_extract_host_checks_multiple_files():
    """Test extraction from multiple project memory files."""
    docs = [
        (
            "LIKECODEX.md",
            """## LikeCodex host checks

- verify: pytest
""",
        ),
        (
            "AGENTS.md",
            """## LikeCodex host checks

- verify: ruff check
""",
        ),
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 2
    assert checks[0].source_path == "LIKECODEX.md"
    assert checks[1].source_path == "AGENTS.md"


def test_extract_host_checks_no_section():
    """Test that documents without the section return empty list."""
    docs = [
        (
            "README.md",
            """# README

This is a regular README without host checks.
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 0


def test_extract_host_checks_asterisk_bullets():
    """Test that asterisk bullets are also parsed."""
    docs = [
        (
            "LIKECODEX.md",
            """## LikeCodex host checks

* verify: pytest
* verify: ruff check
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 2


def test_extract_host_checks_verify_case_insensitive():
    """Test that verify: prefix is case-insensitive."""
    docs = [
        (
            "LIKECODEX.md",
            """## LikeCodex host checks

- VERIFY: pytest
- Verify: ruff check
- verify: mypy
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 3


def test_load_host_checks_from_dir(tmp_path: Path):
    """Test loading host checks from actual files in a directory."""
    likecodex_md = tmp_path / "LIKECODEX.md"
    likecodex_md.write_text(
        """## LikeCodex host checks

- verify: pytest
- verify: ruff check
""",
        encoding="utf-8",
    )

    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        """## LikeCodex host checks

- verify: mypy
""",
        encoding="utf-8",
    )

    checks = load_host_checks_from_dir(tmp_path)
    assert len(checks) == 3
    commands = {c.command for c in checks}
    assert commands == {"pytest", "ruff check", "mypy"}


def test_load_host_checks_from_dir_missing_files(tmp_path: Path):
    """Test that missing files don't cause errors."""
    checks = load_host_checks_from_dir(tmp_path)
    assert len(checks) == 0


def test_extract_host_checks_empty_command():
    """Test that empty commands after verify: are skipped."""
    docs = [
        (
            "LIKECODEX.md",
            """## LikeCodex host checks

- verify:
- verify: pytest
- verify:   
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 1
    assert checks[0].command == "pytest"


def test_extract_host_checks_non_verify_bullets():
    """Test that non-verify bullets are ignored."""
    docs = [
        (
            "LIKECODEX.md",
            """## LikeCodex host checks

- This is a regular bullet
- verify: pytest
- Another regular bullet
- verify: ruff check
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 2


def test_extract_host_checks_section_ends_at_next_heading():
    """Test that the section ends when a new heading starts."""
    docs = [
        (
            "LIKECODEX.md",
            """## LikeCodex host checks

- verify: pytest

## Other section

- verify: ruff check
""",
        )
    ]

    checks = extract_host_checks(docs)
    assert len(checks) == 1
    assert checks[0].command == "pytest"
