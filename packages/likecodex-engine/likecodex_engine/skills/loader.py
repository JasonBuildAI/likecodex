"""Skill discovery and prefix injection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    body: str
    run_as: str = "inline"
    path: Path | None = None
    model: str | None = None
    allowed_tools: list[str] = field(default_factory=list)


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


def _parse_allowed_tools(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.replace(",", " ").split() if part.strip()]


def _load_skill_file(path: Path) -> Skill | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = _parse_frontmatter(text)
    name = meta.get("name", path.stem)
    allowed_raw = meta.get("allowed-tools", meta.get("allowed_tools", ""))
    return Skill(
        name=name,
        description=meta.get("description", name),
        body=body,
        run_as=meta.get("runAs", meta.get("run_as", "inline")),
        path=path,
        model=meta.get("model") or None,
        allowed_tools=_parse_allowed_tools(allowed_raw),
    )


def discover_skills(
    working_dir: str | Path,
    disabled: list[str] | None = None,
) -> list[Skill]:
    disabled_set = {name.strip().lower() for name in (disabled or []) if name.strip()}
    roots: list[Path] = []
    builtins = Path(__file__).resolve().parent / "builtins"
    if builtins.exists():
        roots.append(builtins)
    home = Path.home() / ".likecodex" / "skills"
    project = Path(working_dir) / ".likecodex" / "skills"
    agents_home = Path.home() / ".agents" / "skills"
    agents_project = Path(working_dir) / ".agents" / "skills"
    claude_home = Path.home() / ".claude" / "skills"
    claude_project = Path(working_dir) / ".claude" / "skills"
    for root in (project, agents_project, home, agents_home, claude_home, claude_project):
        if root.exists():
            roots.append(root)

    skills: dict[str, Skill] = {}
    for root in roots:
        if root.name == "builtins":
            for path in sorted(root.glob("*.md")):
                skill = _load_skill_file(path)
                if skill and skill.name.lower() not in disabled_set:
                    skills[skill.name] = skill
            continue
        for path in sorted(root.rglob("*.md")):
            if path.name.upper() == "SKILL.MD" or path.parent.name != "skills":
                skill = _load_skill_file(path)
            else:
                skill = _load_skill_file(path)
            if skill and skill.name.lower() not in disabled_set:
                skills[skill.name] = skill
        for path in sorted(root.glob("*.md")):
            skill = _load_skill_file(path)
            if skill and skill.name.lower() not in disabled_set:
                skills[skill.name] = skill
    return [skills[k] for k in sorted(skills.keys())]


def skills_prefix_block(skills: list[Skill]) -> str:
    """Cache-stable index: names and descriptions only (bodies load on demand)."""
    if not skills:
        return ""
    lines = ["The following skills are available (invoke via run_skill):"]
    for skill in skills:
        extras = []
        if skill.model:
            extras.append(f"model={skill.model}")
        if skill.allowed_tools:
            extras.append(f"allowed-tools={','.join(skill.allowed_tools)}")
        suffix = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"- **{skill.name}**: {skill.description} (runAs={skill.run_as}){suffix}")
    return "\n".join(lines)
