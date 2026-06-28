"""Lifecycle hooks for agent events."""

from __future__ import annotations

import asyncio
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HookDef:
    event: str
    command: str


def _hooks_paths(working_dir: str | Path) -> list[Path]:
    paths = [
        Path.home() / ".likecodex" / "hooks.toml",
        Path(working_dir) / ".likecodex" / "hooks.toml",
    ]
    return [p for p in paths if p.exists()]


def load_hooks(working_dir: str | Path) -> list[HookDef]:
    hooks: list[HookDef] = []
    for path in _hooks_paths(working_dir):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for event, cfg in data.get("hooks", {}).items():
            if isinstance(cfg, dict) and "command" in cfg:
                hooks.append(HookDef(event=event, command=str(cfg["command"])))
            elif isinstance(cfg, str):
                hooks.append(HookDef(event=event, command=cfg))
    return hooks


async def run_hook(hook: HookDef, env: dict[str, str] | None = None) -> str:
    proc = await asyncio.create_subprocess_shell(
        hook.command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, **(env or {})},
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return stdout.decode("utf-8", errors="replace").strip()
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return f"[hook timeout] {hook.command}"


async def fire_hooks(event: str, working_dir: str, payload: dict[str, str] | None = None) -> str:
    env = {"LIKECODEX_HOOK_EVENT": event, "LIKECODEX_WORKING_DIR": str(working_dir)}
    if payload:
        env.update({f"LIKECODEX_{k.upper()}": v for k, v in payload.items()})
    outputs: list[str] = []
    for hook in load_hooks(working_dir):
        if hook.event == event:
            result = await run_hook(hook, env)
            if result:
                outputs.append(result)
    return "\n".join(outputs)
