"""Agent skills discovery and prefix injection."""

from likecodex_engine.skills.loader import (
    Skill,
    discover_skills,
    inject_dynamic_context,
    skills_prefix_block,
)
from likecodex_engine.skills.state import (
    is_skill_enabled,
    load_skill_state,
    save_skill_state,
    set_skill_enabled,
)

__all__ = [
    "Skill",
    "discover_skills",
    "inject_dynamic_context",
    "skills_prefix_block",
    "is_skill_enabled",
    "load_skill_state",
    "save_skill_state",
    "set_skill_enabled",
]
