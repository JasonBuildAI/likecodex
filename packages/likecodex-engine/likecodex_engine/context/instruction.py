"""Extract host-observable project checks from structured project memory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class VerifyCheck:
    """A verification check extracted from project memory."""

    command: str
    source_path: str
    line: int


def extract_host_checks(docs: Iterable[tuple[str, str]]) -> list[VerifyCheck]:
    """Extract host checks from project memory documents.

    Args:
        docs: Iterable of (path, content) tuples representing project memory files.

    Returns:
        List of VerifyCheck objects parsed from "LikeCodex host checks" sections.
    """
    seen: set[str] = set()
    checks: list[VerifyCheck] = []

    for path, content in docs:
        in_section = False
        for i, raw_line in enumerate(content.splitlines()):
            line = raw_line.rstrip()

            # Check for section heading
            if heading := _markdown_heading(line):
                in_section = heading.lower() == "likecodex host checks"
                continue

            if not in_section:
                continue

            # Extract verify: bullet
            if command := _verify_bullet(line):
                if command not in seen:
                    seen.add(command)
                    checks.append(
                        VerifyCheck(
                            command=command,
                            source_path=path,
                            line=i + 1,
                        )
                    )

    return checks


def _markdown_heading(line: str) -> str | None:
    """Parse a markdown heading and return the text, or None if not a heading."""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    hashes = len(stripped) - len(stripped.lstrip("#"))
    # Must have space after # and non-empty content
    if hashes >= len(stripped) or stripped[hashes] != " ":
        return None
    heading = stripped[hashes + 1:].rstrip("#").strip()
    return heading if heading else None


def _verify_bullet(line: str) -> str | None:
    """Parse a verify: bullet point and return the command, or None if not a verify bullet."""
    line = line.strip()
    if len(line) < 2 or (line[:2] != "- " and line[:2] != "* "):
        return None

    body = line[2:].strip()
    prefix = "verify:"

    if len(body) < len(prefix) or not body[: len(prefix)].lower() == prefix:
        return None

    command = body[len(prefix) :].strip()
    return command if command else None


def load_host_checks_from_dir(working_dir: Path) -> list[VerifyCheck]:
    """Load host checks from LIKECODEX.md and AGENTS.md in the given directory.

    Args:
        working_dir: Directory to search for project memory files.

    Returns:
        List of VerifyCheck objects.
    """
    docs: list[tuple[str, str]] = []

    for filename in ["LIKECODEX.md", "AGENTS.md"]:
        path = working_dir / filename
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                docs.append((str(path), content))
            except (OSError, UnicodeDecodeError):
                continue

    return extract_host_checks(docs)
