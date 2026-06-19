"""Project memory file discovery.

LikeCodex pins a hierarchy of memory files into the cache-stable prefix so the
model always sees project conventions. Precedence (later appended after earlier):
the user-global file in ``~/.likecodex`` then the project file in the workspace.
Both ``LIKECODEX.md`` and Claude-style ``AGENTS.md`` are recognised.
"""

from __future__ import annotations

from pathlib import Path

_MEMORY_FILENAMES = ("LIKECODEX.md", "AGENTS.md")
_MAX_MEMORY_CHARS = 16_000


def discover_memory_files(working_dir: str | Path) -> list[Path]:
    """Return existing memory files in precedence order (global first, project last)."""
    found: list[Path] = []
    home = Path.home() / ".likecodex"
    project = Path(working_dir)
    for base in (home, project):
        for name in _MEMORY_FILENAMES:
            candidate = base / name
            if candidate.exists() and candidate.is_file():
                found.append(candidate)
                break  # one per directory; LIKECODEX.md wins over AGENTS.md
    return found


def load_project_memory(working_dir: str | Path) -> str:
    """Read and concatenate discovered memory files (bounded for cache stability)."""
    parts: list[str] = []
    for path in discover_memory_files(working_dir):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            parts.append(text)
    combined = "\n\n".join(parts)
    return combined[:_MAX_MEMORY_CHARS]
