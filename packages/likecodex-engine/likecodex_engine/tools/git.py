"""Git tools for the agent."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class GitTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    async def _run(self, args: str) -> dict[str, Any]:
        command = f"git {args}"
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return {
                "command": command,
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {"command": command, "exit_code": None, "error": str(e)}

    def status_schema(self) -> dict[str, Any]:
        return {
            "description": "Get git status of the working directory.",
            "parameters": {"type": "object", "properties": {}},
        }

    async def git_status(self) -> str:
        result = await self._run("status --porcelain -b")
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
        result = await self._run(f"diff {target}")
        return json.dumps(result)

    def log_schema(self) -> dict[str, Any]:
        return {
            "description": "Get recent git commit log.",
            "parameters": {
                "type": "object",
                "properties": {"count": {"type": "integer", "default": 10, "description": "Number of commits to show"}},
            },
        }

    async def git_log(self, count: int = 10) -> str:
        result = await self._run(f"log --oneline -n {count}")
        return json.dumps(result)

    def branch_schema(self) -> dict[str, Any]:
        return {
            "description": "Get current git branch.",
            "parameters": {"type": "object", "properties": {}},
        }

    async def git_branch(self) -> str:
        result = await self._run("branch --show-current")
        return json.dumps(result)

    def commit_schema(self) -> dict[str, Any]:
        return {
            "description": "Commit staged changes with a message (auto-generates if empty).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message (optional, auto-generated if empty)"},
                    "all": {"type": "boolean", "default": True, "description": "Stage all changes before commit"},
                    "auto_message": {"type": "boolean", "default": True, "description": "Auto-generate commit message from diff"},
                },
                "required": [],
            },
        }

    async def git_commit(self, message: str = "", add_all: bool = True, auto_message: bool = True) -> str:
        if add_all:
            await self._run("add -A")
        if auto_message and not message:
            diff_result = await self._run("diff --cached --stat")
            if diff_result.get("exit_code") == 0 and diff_result.get("stdout"):
                first_line = diff_result["stdout"].strip().split("\n")[0]
                message = f"Auto-commit: {first_line[:80]}"
            else:
                message = "Auto-commit"
        escaped_message = message.replace('"', '\\"')
        result = await self._run(f'commit -m "{escaped_message}"')
        return json.dumps(result)
