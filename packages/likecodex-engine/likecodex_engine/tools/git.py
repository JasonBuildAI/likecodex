"""Git tools for the agent."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class GitTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    async def _run(self, args: list[str]) -> dict[str, Any]:
        command_display = "git " + " ".join(args)
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return {
                "command": command_display,
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {"command": command_display, "exit_code": None, "error": str(e)}

    def status_schema(self) -> dict[str, Any]:
        return {
            "description": "Get git status of the working directory.",
            "parameters": {"type": "object", "properties": {}},
        }

    async def git_status(self) -> str:
        result = await self._run(["status", "--porcelain", "-b"])
        return json.dumps(result)

    def diff_schema(self) -> dict[str, Any]:
        return {
            "description": "Get git diff against a target (default HEAD).",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string", "default": "HEAD"}},
            },
        }

    async def git_diff(self, target: str = "HEAD") -> str:
        if target.startswith("-"):
            return json.dumps({"error": "Invalid diff target"})
        result = await self._run(["diff", target])
        return json.dumps(result)

    def log_schema(self) -> dict[str, Any]:
        return {
            "description": "Get recent git commit log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "default": 10, "description": "Number of commits to show"},
                },
            },
        }

    async def git_log(self, count: int = 10) -> str:
        count = max(1, min(int(count), 100))
        result = await self._run(["log", "--oneline", "-n", str(count)])
        return json.dumps(result)

    def branch_schema(self) -> dict[str, Any]:
        return {
            "description": "Get current git branch.",
            "parameters": {"type": "object", "properties": {}},
        }

    async def git_branch(self) -> str:
        result = await self._run(["branch", "--show-current"])
        return json.dumps(result)

    def commit_schema(self) -> dict[str, Any]:
        return {
            "description": "Commit staged changes with a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "all": {"type": "boolean", "default": False, "description": "Stage all changes before commit"},
                },
                "required": ["message"],
            },
        }

    async def git_commit(self, message: str, all: bool = False) -> str:
        if all:
            await self._run(["add", "-A"])
        result = await self._run(["commit", "-m", message, "--"])
        return json.dumps(result)
