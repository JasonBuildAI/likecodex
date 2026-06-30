"""Skill discovery and prefix injection.

Follows the agentskills.io open standard for SKILL.md files.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Skill:
    """Represents a single agent skill loaded from a SKILL.md file."""

    name: str
    description: str
    body: str
    run_as: str = "inline"
    path: Path | None = None
    model: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    # agentskills.io extended fields
    license: str = ""
    compatibility: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    version: str = ""
    author: str = ""
    # Management fields
    enabled: bool = True
    source_type: str = "project"  # project | home | builtin
    source_dir: Path | None = None  # parent directory for directory-format skills

    @property
    def source(self) -> str:
        """Backward-compatible source label derived from source_type."""
        return self.source_type

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict (Paths → strings)."""
        d = asdict(self)
        d["path"] = str(self.path) if self.path else None
        d["source_dir"] = str(self.source_dir) if self.source_dir else None
        d["source"] = self.source
        return d


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a SKILL.md file.

    Uses PyYAML for proper nested structures (metadata dict, lists, etc.)
    with a fallback to the naive parser if PyYAML is unavailable.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    yaml_block = parts[1].strip()
    body = parts[2].strip()
    try:
        import yaml
        meta = yaml.safe_load(yaml_block)
        if not isinstance(meta, dict):
            meta = {}
        return meta, body
    except ImportError:
        # Fallback: naive line-by-line parser
        meta: dict = {}
        for line in yaml_block.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()
        return meta, body
    except Exception:
        return {}, body


def _parse_allowed_tools(raw) -> list[str]:
    """Parse allowed-tools from frontmatter (string, list, or None)."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if t]
    return [part.strip() for part in str(raw).replace(",", " ").split() if part.strip()]


def _infer_source_type(path: Path) -> str:
    """Derive source_type from path location."""
    parts = str(path).replace("\\", "/")
    if "builtins" in parts:
        return "builtin"
    home = str(Path.home()).replace("\\", "/")
    if parts.startswith(home):
        return "home"
    return "project"


def _load_skill_file(path: Path) -> Skill | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = _parse_frontmatter(text)
    name = meta.get("name", path.stem)
    allowed_raw = meta.get("allowed-tools", meta.get("allowed_tools", ""))
    # Parse metadata dict from frontmatter
    raw_meta = meta.get("metadata", "")
    meta_dict: dict[str, str] = {}
    if isinstance(raw_meta, dict):
        meta_dict = {str(k): str(v) for k, v in raw_meta.items()}
    elif isinstance(raw_meta, str) and raw_meta:
        try:
            parsed = json.loads(raw_meta)
            if isinstance(parsed, dict):
                meta_dict = {str(k): str(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, ValueError):
            pass
    return Skill(
        name=name,
        description=meta.get("description", name),
        body=body,
        run_as=meta.get("runAs", meta.get("run_as", "inline")),
        path=path,
        model=meta.get("model") or None,
        allowed_tools=_parse_allowed_tools(allowed_raw),
        license=meta.get("license", ""),
        compatibility=meta.get("compatibility", ""),
        metadata=meta_dict,
        version=meta.get("version", ""),
        author=meta.get("author", ""),
        source_type=_infer_source_type(path),
    )


def _load_skill_directory(dir_path: Path) -> Skill | None:
    """Load a skill from a directory containing SKILL.md (agentskills.io format)."""
    skill_md = dir_path / "SKILL.md"
    if not skill_md.is_file():
        return None
    skill = _load_skill_file(skill_md)
    if skill is None:
        return None
    # Override name with directory name if not explicitly set in frontmatter
    if not skill.name or skill.name == "SKILL":
        skill.name = dir_path.name
    skill.source_dir = dir_path
    skill.source_type = _infer_source_type(dir_path)
    return skill


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
        is_builtin = root.name == "builtins"
        # Scan directory-format skills: <name>/SKILL.md
        if not is_builtin:
            for child in sorted(root.iterdir()) if root.is_dir() else []:
                if child.is_dir() and (child / "SKILL.md").is_file():
                    skill = _load_skill_directory(child)
                    if skill and skill.name.lower() not in disabled_set:
                        skills[skill.name] = skill
        # Scan flat-file skills: *.md
        if is_builtin:
            for path in sorted(root.glob("*.md")):
                skill = _load_skill_file(path)
                if skill and skill.name.lower() not in disabled_set:
                    skills[skill.name] = skill
        else:
            for path in sorted(root.glob("*.md")):
                # Skip SKILL.md inside subdirs (already handled above)
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
        if not skill.enabled:
            continue
        extras = []
        if skill.model:
            extras.append(f"model={skill.model}")
        if skill.allowed_tools:
            extras.append(f"allowed-tools={','.join(skill.allowed_tools)}")
        suffix = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"- **{skill.name}**: {skill.description} (runAs={skill.run_as}){suffix}")
    return "\n".join(lines)


def inject_dynamic_context(body: str, skill_dir: Path | None = None) -> str:
    """Process dynamic context injection syntax in SKILL.md body.

    Replaces `` !`command` `` patterns with the stdout of executing
    that command (with a 10s timeout). Only executed at skill load
    time, not during discovery.
    """
    pattern = re.compile(r'!`([^`]+)`')
    matches = list(pattern.finditer(body))
    if not matches:
        return body
    result = body
    for match in reversed(matches):
        cmd = match.group(1).strip()
        # Replace ${SKILL_DIR} variable
        if skill_dir:
            cmd = cmd.replace("${SKILL_DIR}", str(skill_dir))
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(skill_dir) if skill_dir else None,
            )
            output = proc.stdout.strip()
            if proc.returncode != 0 and proc.stderr:
                output = f"[error: {proc.stderr.strip()}]"
        except subprocess.TimeoutExpired:
            output = "[error: command timed out after 10s]"
        except Exception as e:
            output = f"[error: {e}]"
        result = result[:match.start()] + output + result[match.end():]
    return result
