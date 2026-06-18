"""Shared path resolution helpers for tool safety."""

from __future__ import annotations

from pathlib import Path

MAX_READ_BYTES = 1_048_576  # 1 MiB

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "target"}


def resolve_in_working_dir(working_dir: Path, path: str) -> Path:
    """Resolve a path and ensure it stays within the working directory."""
    target = Path(path)
    if not target.is_absolute():
        target = working_dir / target
    resolved = target.resolve()
    try:
        resolved.relative_to(working_dir)
    except ValueError as exc:
        raise PermissionError(f"Path escapes working directory: {path}") from exc
    return resolved


def should_skip_path(working_dir: Path, path: Path) -> bool:
    """Return True if the path is under a skipped directory."""
    try:
        parts = path.relative_to(working_dir).parts
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in parts)
