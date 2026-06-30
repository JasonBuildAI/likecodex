"""Skill enable/disable state persistence.

Stores per-project skill state in .likecodex/skills-state.json to avoid
modifying SKILL.md files directly, keeping skills portable and git-friendly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _state_path(working_dir: str | Path) -> Path:
    """Return the path to the skills state file for a working directory."""
    return Path(working_dir) / ".likecodex" / "skills-state.json"


def load_skill_state(working_dir: str | Path) -> dict[str, dict]:
    """Load skill state map from disk.

    Returns a dict of {skill_name: {enabled: bool, ...}}.
    """
    path = _state_path(working_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load skills state: %s", e)
    return {}


def save_skill_state(working_dir: str | Path, state: dict[str, dict]) -> None:
    """Persist skill state map to disk."""
    path = _state_path(working_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def is_skill_enabled(working_dir: str | Path, name: str) -> bool:
    """Check if a skill is enabled (default True if no state recorded)."""
    state = load_skill_state(working_dir)
    entry = state.get(name)
    if entry is None:
        return True
    return bool(entry.get("enabled", True))


def set_skill_enabled(working_dir: str | Path, name: str, enabled: bool) -> None:
    """Set the enabled state for a skill."""
    state = load_skill_state(working_dir)
    if name not in state:
        state[name] = {}
    state[name]["enabled"] = enabled
    save_skill_state(working_dir, state)
