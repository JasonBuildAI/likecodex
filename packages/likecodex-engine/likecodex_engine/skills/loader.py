"""Skill discovery and prefix injection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    body: str
    run_as: str = "inline"
    path: Path | None = None


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()
    return meta, parts[2].strip()


def _load_skill_file(path: Path) -> Skill | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = _parse_frontmatter(text)
    name = meta.get("name", path.stem)
    return Skill(
        name=name,
        description=meta.get("description", name),
        body=body,
        run_as=meta.get("runAs", meta.get("run_as", "inline")),
        path=path,
    )


def discover_skills(working_dir: str | Path) -> list[Skill]:
    roots: list[Path] = []
    home = Path.home() / ".likecodex" / "skills"
    project = Path(working_dir) / ".likecodex" / "skills"
    claude_home = Path.home() / ".claude" / "skills"
    claude_project = Path(working_dir) / ".claude" / "skills"
    for root in (home, project, claude_home, claude_project):
        if root.exists():
            roots.append(root)

    skills: dict[str, Skill] = {}
    for root in roots:
        for path in sorted(root.rglob("*.md")):
            if path.name.upper() == "SKILL.MD" or path.parent.name != "skills":
                skill = _load_skill_file(path)
            else:
                skill = _load_skill_file(path)
            if skill:
                skills[skill.name] = skill
        for path in sorted(root.glob("*.md")):
            skill = _load_skill_file(path)
            if skill:
                skills[skill.name] = skill
    return [skills[k] for k in sorted(skills.keys())]


def skills_prefix_block(skills: list[Skill]) -> str:
    if not skills:
        return ""
    lines = ["The following skills are available:"]
    for skill in skills:
        lines.append(f"- **{skill.name}**: {skill.description} (runAs={skill.run_as})")
        if skill.run_as == "inline" and skill.body:
            lines.append(skill.body[:500])
    return "\n".join(lines)
