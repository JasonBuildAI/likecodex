"""Slash commands, @-references, and project memory bootstrap (/init).

These are prompt-preprocessing features shared by the CLI and Web UI: both send
raw user input to the engine, and the engine expands it before the agent runs.

- Custom slash commands live in ``.likecodex/commands/<name>.md``; ``/<name> args``
  expands to the file's body with ``$ARGS`` / ``$1`` placeholders substituted.
- ``@path`` tokens inject the referenced file or directory listing as context.
- ``/init`` scans the workspace and writes a ``LIKECODEX.md`` project memory file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from likecodex_engine.tools.encoding import read_text_detect

_AT_RE = re.compile(r"(?<!\S)@([\w./\\-]+)")
_MAX_REF_CHARS = 12_000
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "target", "dist", "build"}

_EXACT_COMMANDS: dict[str, ExpandedPrompt] = {}  # populated lazily in expand_prompt


def _build_exact_commands() -> dict[str, ExpandedPrompt]:
    """Build dispatch table for exact-match slash commands."""
    return {
        "/plan": ExpandedPrompt(
            prompt="Enter plan mode: explore read-only, then produce an execution plan.",
            plan_mode_enter=True,
            direct_reply=(
                "Plan mode enabled. Write tools and risky shell commands are blocked until you exit plan mode."
            ),
        ),
        "/exit_plan approve": ExpandedPrompt(
            prompt="Approve exiting plan mode.",
            plan_mode_exit_approve=True,
            direct_reply="Plan mode disabled. Write tools are available again.",
        ),
        "/goal clear": ExpandedPrompt(prompt="/goal clear", goal_clear=True, direct_reply="Active goal cleared."),
        "/goal --clear": ExpandedPrompt(prompt="/goal --clear", goal_clear=True, direct_reply="Active goal cleared."),
    }


@dataclass
class ExpandedPrompt:
    prompt: str
    context_blocks: list[str] = field(default_factory=list)
    direct_reply: str | None = None  # set when a command handled the request itself
    plan_mode_enter: bool = False
    plan_mode_exit_request: bool = False
    plan_mode_exit_approve: bool = False
    compact_trigger: bool = False
    compact_focus: str = ""
    goal_start: str | None = None
    goal_strategy: str = "simple"
    goal_clear: bool = False


def load_slash_commands(working_dir: str | Path) -> dict[str, str]:
    """Load user-defined slash commands from .likecodex/commands/*.md."""
    commands: dict[str, str] = {}
    base = Path(working_dir) / ".likecodex" / "commands"
    if not base.is_dir():
        return commands
    for md in sorted(base.glob("*.md")):
        try:
            commands[md.stem] = md.read_text(encoding="utf-8")
        except OSError:
            continue
    return commands


def _expand_slash(prompt: str, commands: dict[str, str]) -> str:
    stripped = prompt.lstrip()
    if not stripped.startswith("/"):
        return prompt
    head, _, rest = stripped[1:].partition(" ")
    body = commands.get(head)
    if body is None:
        return prompt
    args = rest.strip()
    arg_parts = args.split()
    expanded = body.replace("$ARGS", args)
    for i, part in enumerate(arg_parts, start=1):
        expanded = expanded.replace(f"${i}", part)
    return expanded


def _expand_at_references(prompt: str, working_dir: Path) -> list[str]:
    blocks: list[str] = []
    seen: set[str] = set()
    for match in _AT_RE.finditer(prompt):
        ref = match.group(1)
        if ref in seen:
            continue
        seen.add(ref)
        target = (working_dir / ref).resolve()
        try:
            target.relative_to(working_dir)
        except ValueError:
            continue
        if not target.exists():
            continue
        if target.is_dir():
            entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir() if p.name not in _SKIP_DIRS)
            blocks.append(f"@{ref} (directory):\n" + "\n".join(entries))
        else:
            try:
                text = read_text_detect(target).text
            except OSError:
                continue
            blocks.append(f"@{ref}:\n```\n{text[:_MAX_REF_CHARS]}\n```")
    return blocks


def expand_prompt(prompt: str, working_dir: str | Path) -> ExpandedPrompt:
    """Apply slash-command expansion, /init handling, and @-reference injection."""
    wd = Path(working_dir).resolve()
    stripped = prompt.strip()

    if stripped == "/init" or stripped.startswith("/init "):
        path = generate_project_memory(wd)
        return ExpandedPrompt(
            prompt=prompt,
            direct_reply=f"Generated project memory at {path.name}. Edit it to capture conventions.",
        )

    if stripped == "/compact" or stripped.startswith("/compact "):
        focus = stripped.removeprefix("/compact").strip()
        return ExpandedPrompt(
            prompt=prompt,
            compact_trigger=True,
            compact_focus=focus,
        )

    exact = _build_exact_commands().get(stripped)
    if exact is not None:
        return exact

    if stripped == "/exit_plan" or stripped.startswith("/exit_plan "):
        plan_text = stripped.replace("/exit_plan", "").strip()
        return ExpandedPrompt(
            prompt=plan_text or "Submit plan for approval before exiting plan mode.",
            plan_mode_exit_request=True,
            direct_reply=(
                "Plan exit requested. Review the plan summary, then send `/exit_plan approve` to leave plan mode."
            ),
        )

    if stripped.startswith("/goal"):
        rest = stripped.removeprefix("/goal").strip()
        strategy = "simple"
        if rest.startswith("--research"):
            strategy = "research"
            rest = rest.removeprefix("--research").strip()
        elif rest.startswith("--simple"):
            strategy = "simple"
            rest = rest.removeprefix("--simple").strip()
        objective = rest or "Continue the active goal."
        return ExpandedPrompt(
            prompt=objective,
            goal_start=objective,
            goal_strategy=strategy,
            direct_reply=f"Goal mode started ({strategy}): {objective}",
        )

    commands = load_slash_commands(wd)
    expanded = _expand_slash(prompt, commands)
    blocks = _expand_at_references(expanded, wd)
    return ExpandedPrompt(prompt=expanded, context_blocks=blocks)


def generate_project_memory(working_dir: str | Path) -> Path:
    """Scan the workspace and write a starter LIKECODEX.md memory file."""
    wd = Path(working_dir).resolve()
    target = wd / "LIKECODEX.md"

    languages: dict[str, int] = {}
    top_dirs: list[str] = []
    file_count = 0
    for entry in sorted(wd.iterdir()):
        if entry.name in _SKIP_DIRS or entry.name.startswith("."):
            continue
        if entry.is_dir():
            top_dirs.append(entry.name + "/")
    for path in wd.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        file_count += 1
        ext = path.suffix.lower()
        if ext:
            languages[ext] = languages.get(ext, 0) + 1

    top_langs = sorted(languages.items(), key=lambda kv: kv[1], reverse=True)[:8]
    lang_lines = "\n".join(f"- `{ext}`: {count} files" for ext, count in top_langs)
    dir_lines = "\n".join(f"- `{d}`" for d in top_dirs[:20]) or "- (flat layout)"

    content = f"""# Project Memory

> Generated by `likecodex /init`. Edit this file to record project-specific
> conventions, architecture notes, and instructions the agent should always follow.
> This file is pinned into the model's cache-stable prefix.

## Overview

- Workspace: `{wd.name}`
- Tracked files: ~{file_count}

## Layout

{dir_lines}

## Dominant file types

{lang_lines}

## Conventions (fill in)

- Build/test commands:
- Code style:
- Things to avoid:

## LikeCodex host checks

> Commands listed here are treated as final-readiness gates: the agent must
> run each verification command successfully before it may stop with a final
> answer. Use `verify:` prefix for each bullet.

- verify: echo "add your verification commands here"
"""
    target.write_text(content, encoding="utf-8")
    return target
