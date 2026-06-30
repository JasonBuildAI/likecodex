"""Skill CRUD manager for creating, updating, deleting, and installing skills.

Provides high-level operations used by the HTTP API layer.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import textwrap
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,63}$")


def validate_skill_name(name: str) -> str | None:
    """Return None if valid, otherwise an error message."""
    if not NAME_RE.match(name):
        return (
            "Invalid name. Must be 1-64 lowercase alphanumeric characters "
            "or hyphens, starting with a letter or digit."
        )
    return None


def _skills_dir(working_dir: str | Path) -> Path:
    """Return the project-level skills directory."""
    return Path(working_dir) / ".likecodex" / "skills"


def create_skill(
    working_dir: str | Path,
    name: str,
    description: str = "",
    body: str = "",
    run_as: str = "inline",
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    author: str = "",
    version: str = "0.1.0",
) -> Path:
    """Create a new skill as a directory-format SKILL.md.

    Returns the path to the created SKILL.md file.
    """
    err = validate_skill_name(name)
    if err:
        raise ValueError(err)

    skill_dir = _skills_dir(working_dir) / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Build YAML frontmatter
    fm_lines = [
        "---",
        f"name: {name}",
        f'description: "{description}"',
        f"runAs: {run_as}",
    ]
    if model:
        fm_lines.append(f"model: {model}")
    if allowed_tools:
        fm_lines.append("allowed-tools:")
        for t in allowed_tools:
            fm_lines.append(f"  - {t}")
    if author:
        fm_lines.append(f"author: {author}")
    if version:
        fm_lines.append(f"version: {version}")
    fm_lines.append("---")

    content = "\n".join(fm_lines) + "\n\n" + body
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


def update_skill(
    working_dir: str | Path,
    name: str,
    **fields: str | list[str] | None,
) -> Path | None:
    """Update specific fields of an existing skill.

    Supported keyword args: name, description, body, run_as, model, allowed_tools.
    Returns the path to the updated SKILL.md, or None if not found.
    """
    skill_md = _find_skill_file(working_dir, name)
    if skill_md is None:
        return None

    text = skill_md.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            yaml_block = parts[1].strip()
            body_block = parts[2]

            import yaml

            try:
                meta = yaml.safe_load(yaml_block) or {}
            except Exception:
                meta = {}

            if "description" in fields and fields["description"] is not None:
                meta["description"] = fields["description"]
            if "run_as" in fields and fields["run_as"] is not None:
                meta["runAs"] = fields["run_as"]
            if "model" in fields:
                meta["model"] = fields["model"]
            if "allowed_tools" in fields and fields["allowed_tools"] is not None:
                meta["allowed-tools"] = list(fields["allowed_tools"])

            # Rebuild YAML
            fm_lines = ["---"]
            for key in ("name", "description", "runAs", "model", "author", "version", "license"):
                if key in meta and meta[key]:
                    if key == "description":
                        fm_lines.append(f'{key}: "{meta[key]}"')
                    else:
                        fm_lines.append(f"{key}: {meta[key]}")
            if "allowed-tools" in meta and meta["allowed-tools"]:
                fm_lines.append("allowed-tools:")
                for t in meta["allowed-tools"]:
                    fm_lines.append(f"  - {t}")
            fm_lines.append("---")

            new_body = fields.get("body", body_block)
            if new_body is None:
                new_body = body_block
            content = "\n".join(fm_lines) + new_body
            skill_md.write_text(content, encoding="utf-8")

            # Handle rename
            new_name = fields.get("name")
            if new_name and new_name != name:
                err = validate_skill_name(str(new_name))
                if err:
                    raise ValueError(err)
                new_dir = skill_md.parent.parent / str(new_name)
                if new_dir.exists():
                    raise ValueError(f"Skill directory {new_name!r} already exists")
                skill_md.parent.rename(new_dir)
                skill_md = new_dir / "SKILL.md"

            return skill_md
    return skill_md


def delete_skill(working_dir: str | Path, name: str) -> bool:
    """Delete a skill. Returns False if built-in or not found."""
    skill_md = _find_skill_file(working_dir, name)
    if skill_md is None:
        return False
    # Check if built-in (not allowed to delete)
    if "builtins" in str(skill_md).replace("\\", "/"):
        raise PermissionError("Cannot delete built-in skills")

    # Remove directory format or single file
    if skill_md.name == "SKILL.md" and skill_md.parent.name == name:
        shutil.rmtree(skill_md.parent, ignore_errors=True)
    else:
        skill_md.unlink(missing_ok=True)
    return True


def install_skill_from_url(working_dir: str | Path, url: str) -> Path:
    """Clone a skill from a Git URL into the project skills directory."""
    skills_dir = _skills_dir(working_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Extract name from URL
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    target = skills_dir / name
    if target.exists():
        raise FileExistsError(f"Skill {name!r} already exists at {target}")

    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(target)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()}")

    # Clean up .git directory inside the skill
    git_dir = target / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, ignore_errors=True)

    return target


def export_skill(working_dir: str | Path, name: str) -> bytes:
    """Export a skill as a zip archive."""
    import io

    skill_md = _find_skill_file(working_dir, name)
    if skill_md is None:
        raise FileNotFoundError(f"Skill {name!r} not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if skill_md.parent.name == name:
            # Directory format
            for f in sorted(skill_md.parent.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(skill_md.parent).as_posix())
        else:
            # Flat file
            zf.write(skill_md, skill_md.name)
    return buf.getvalue()


def import_skill(working_dir: str | Path, zip_data: bytes) -> list[str]:
    """Import skills from a zip archive. Returns list of imported skill names."""
    import io

    skills_dir = _skills_dir(working_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)

    buf = io.BytesIO(zip_data)
    imported: list[str] = []
    with zipfile.ZipFile(buf, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            # Determine target
            if "/" in name:
                # Directory-format skill: <skill-name>/SKILL.md
                skill_name = name.split("/")[0]
                target = skills_dir / skill_name / Path(name).name
            else:
                target = skills_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            if name.endswith("SKILL.md"):
                imported.append(target.parent.name if target.name == "SKILL.md" else target.stem)
    return imported


def _find_skill_file(working_dir: str | Path, name: str) -> Path | None:
    """Locate the SKILL.md or <name>.md for a given skill name."""
    from likecodex_engine.skills.loader import discover_skills

    skills = discover_skills(working_dir)
    skill = next((s for s in skills if s.name == name), None)
    if skill and skill.path and skill.path.is_file():
        return skill.path
    # Fallback: direct path check
    base = _skills_dir(working_dir)
    for candidate in (base / name / "SKILL.md", base / f"{name}.md"):
        if candidate.is_file():
            return candidate
    return None
