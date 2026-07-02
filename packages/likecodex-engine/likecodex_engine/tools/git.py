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

    async def _generate_commit_message(self) -> str:
        """Generate a descriptive commit message from the staged diff.

        Analyzes file changes to determine type and creates a meaningful message.
        """
        # Get diff stat for file-level overview
        stat_result = await self._run("diff --cached --stat")
        if stat_result.get("exit_code") != 0 or not stat_result.get("stdout"):
            return "Auto-commit"

        stat_lines = stat_result["stdout"].strip().split("\n")
        changed_files = []
        for line in stat_lines:
            if "|" in line and not line.startswith(" "):
                fname = line.split("|")[0].strip()
                changed_files.append(fname)

        if not changed_files:
            # Check for new untracked files
            status_result = await self._run("status --porcelain")
            if status_result.get("stdout"):
                return "Auto-commit: new changes"
            return "Auto-commit"

        # Determine commit type from file extensions
        type_indicators = {
            "feat": [".py", ".rs", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"],
            "fix": [],
            "docs": [".md", ".rst", ".txt"],
            "test": ["test_", "_test", ".spec.", ".test."],
            "config": [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
            "style": [".css", ".scss", ".less", ".sass"],
        }

        # Detect primary type
        commit_type = "chore"
        has_feat = False
        has_fix = False
        has_docs = False
        has_test = False
        has_config = False

        for fname in changed_files:
            lower_fname = fname.lower()
            if any(lower_fname.endswith(ext) for ext in type_indicators["feat"]):
                has_feat = True
            if "fix" in lower_fname or "bug" in lower_fname or "hotfix" in lower_fname:
                has_fix = True
            if any(lower_fname.endswith(ext) for ext in type_indicators["docs"]):
                has_docs = True
            if any(kw in lower_fname for kw in type_indicators["test"]):
                has_test = True
            if any(lower_fname.endswith(ext) for ext in type_indicators["config"]):
                has_config = True

        if has_feat:
            commit_type = "feat"
        elif has_fix:
            commit_type = "fix"
        elif has_docs:
            commit_type = "docs"
        elif has_test:
            commit_type = "test"
        elif has_config:
            commit_type = "chore"

        # Extract changed directory/module name for scope
        scopes = set()
        for fname in changed_files:
            parts = fname.replace("\\", "/").split("/")
            if len(parts) >= 2:
                scopes.add(parts[0])

        scope_str = f"({', '.join(sorted(scopes)[:3])})" if scopes else ""

        # Use the first changed file for description
        first_file = Path(changed_files[0]).stem.replace("_", " ").replace("-", " ")
        file_count = len(changed_files)

        if file_count == 1:
            desc = first_file[:60]
        else:
            desc = f"{first_file[:40]} +{file_count - 1} more"

        message = f"{commit_type}{scope_str}: {desc}"
        return message[:100]

    async def git_commit(self, message: str = "", add_all: bool = True, auto_message: bool = True) -> str:
        if add_all:
            await self._run("add -A")

        # Check if there's anything to commit
        status_result = await self._run("status --porcelain")
        if not status_result.get("stdout", "").strip():
            return json.dumps({
                "command": "git commit",
                "exit_code": 0,
                "stdout": "Nothing to commit, working tree clean",
                "stderr": "",
            })

        if auto_message and not message:
            message = await self._generate_commit_message()

        if not message:
            message = "Auto-commit"

        escaped_message = message.replace('"', '\\"')
        result = await self._run(f'commit -m "{escaped_message}"')
        return json.dumps(result)

    def compare_schema(self) -> dict[str, Any]:
        return {
            "description": "Compare two git refs (branches, tags, commits). Shows ahead/behind info and diff stats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Base ref to compare from (default: current branch)",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target ref to compare against (default: main/master)",
                    },
                },
                "required": [],
            },
        }

    async def git_compare(self, base: str = "", target: str = "main") -> str:
        """Compare two git refs. Returns JSON with commits ahead/behind and diff stats."""
        # Auto-detect default branch
        if target == "main":
            # Try main first, then master
            branch_check = await self._run("rev-parse --verify main")
            if branch_check.get("exit_code") != 0:
                target = "master"

        if not base:
            base_result = await self._run("branch --show-current")
            base = base_result.get("stdout", "").strip()
            if not base:
                base = "HEAD"

        result: dict[str, Any] = {
            "base": base,
            "target": target,
        }

        # Get ahead/behind counts
        rev_result = await self._run(f"rev-list --left-right --count {base}...{target}")
        if rev_result.get("exit_code") == 0 and rev_result.get("stdout"):
            parts = rev_result["stdout"].strip().split()
            if len(parts) == 2:
                result["ahead"] = int(parts[0])
                result["behind"] = int(parts[1])

        # Get commits in base not in target
        ahead_result = await self._run(
            f"log --oneline --no-decorate {target}..{base}"
        )
        if ahead_result.get("exit_code") == 0:
            commits = [
                c.strip()
                for c in ahead_result["stdout"].strip().split("\n")
                if c.strip()
            ]
            result["commits_ahead"] = commits[:50]

        # Get commits in target not in base
        behind_result = await self._run(
            f"log --oneline --no-decorate {base}..{target}"
        )
        if behind_result.get("exit_code") == 0:
            commits = [
                c.strip()
                for c in behind_result["stdout"].strip().split("\n")
                if c.strip()
            ]
            result["commits_behind"] = commits[:50]

        # Get diff stat between the two refs
        diff_result = await self._run(f"diff --stat {base}...{target}")
        if diff_result.get("exit_code") == 0:
            stat_lines = [
                l for l in diff_result["stdout"].strip().split("\n") if l.strip()
            ]
            result["diff_stat"] = stat_lines

        return json.dumps(result, ensure_ascii=False)
