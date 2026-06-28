"""Git Service — provides git status, diff, stage, commit, log, branch operations.

Uses subprocess to run git commands (porcelain format for parsing).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GitChange:
    """A single file change in git status."""

    path: str
    change_type: str  # modified, added, deleted, untracked, renamed
    staged: bool
    old_path: str = ""


@dataclass
class GitCommit:
    """A git commit entry."""

    hash: str
    short_hash: str
    message: str
    author: str
    date: str
    files: list[str] = field(default_factory=list)


@dataclass
class GitBranch:
    """A git branch."""

    name: str
    current: bool
    remote: bool
    last_commit: str = ""


class GitService:
    """Git operations service using subprocess."""

    def __init__(self, working_dir: str) -> None:
        self.working_dir = str(Path(working_dir).resolve())

    async def _run_git(self, *args: str) -> tuple[int, str, str]:
        """Run a git command and return (exit_code, stdout, stderr)."""
        cmd = ["git", *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return (
                proc.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except Exception as exc:
            return (1, "", str(exc))

    def _is_repo(self) -> bool:
        """Check if working_dir is a git repo."""
        git_dir = Path(self.working_dir) / ".git"
        return git_dir.exists()

    async def get_status(self) -> dict[str, Any]:
        """Get git status as structured data."""
        if not self._is_repo():
            return {"changes": [], "current_branch": "", "is_repo": False}

        code, out, _ = await self._run_git("status", "--porcelain=v1", "-b", "-z")
        if code != 0:
            return {"changes": [], "current_branch": "", "is_repo": False}

        changes: list[dict[str, Any]] = []
        entries = out.split("\0")
        i = 0
        while i < len(entries):
            entry = entries[i]
            if not entry:
                i += 1
                continue

            if len(entry) < 3:
                i += 1
                continue

            x = entry[0]  # staged status
            y = entry[1]  # unstaged status
            path = entry[3:]

            # Handle renames
            old_path = ""
            if x == "R" or y == "R":
                i += 1
                old_path = entries[i] if i < len(entries) else ""

            # Determine change type and staged status
            staged = False
            change_type = "modified"

            if x == "M":
                staged = True
                change_type = "modified"
            elif x == "A":
                staged = True
                change_type = "added"
            elif x == "D":
                staged = True
                change_type = "deleted"
            elif x == "R":
                staged = True
                change_type = "renamed"
            elif y == "M":
                change_type = "modified"
            elif y == "D":
                change_type = "deleted"
            elif x == "?" or y == "?":
                change_type = "untracked"
            elif x == "A" and y == "A":
                change_type = "both-added"
                staged = True

            changes.append({
                "path": path,
                "changeType": change_type,
                "staged": staged,
                "oldPath": old_path,
            })
            i += 1

        # Get current branch
        _, branch_out, _ = await self._run_git("branch", "--show-current")
        branch = branch_out.strip()

        return {
            "changes": changes,
            "currentBranch": branch,
            "isRepo": True,
        }

    async def get_diff(self, path: str, staged: bool = False) -> dict[str, Any]:
        """Get diff for a specific file."""
        args = ["diff"]
        if staged:
            args.append("--cached")
        args.extend(["--", path])

        code, out, _ = await self._run_git(*args)

        # Read current file content
        full_path = Path(self.working_dir) / path
        modified_content = ""
        try:
            modified_content = full_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, FileNotFoundError):
            pass

        # Get original content (from HEAD)
        if not staged:
            _, orig_content, _ = await self._run_git("show", f"HEAD:{path}")
        else:
            orig_content = ""

        return {
            "path": path,
            "diff": out,
            "originalContent": orig_content,
            "modifiedContent": modified_content,
        }

    async def stage_file(self, path: str) -> dict[str, Any]:
        """Stage a file."""
        code, _, err = await self._run_git("add", "--", path)
        return {"success": code == 0, "error": err if code != 0 else ""}

    async def unstage_file(self, path: str) -> dict[str, Any]:
        """Unstage a file."""
        code, _, err = await self._run_git("reset", "HEAD", "--", path)
        return {"success": code == 0, "error": err if code != 0 else ""}

    async def stage_all(self) -> dict[str, Any]:
        """Stage all changes."""
        code, _, err = await self._run_git("add", "-A")
        return {"success": code == 0, "error": err if code != 0 else ""}

    async def commit(self, message: str, author: str = "", email: str = "") -> dict[str, Any]:
        """Commit staged changes."""
        args = ["commit", "-m", message]
        if author and email:
            args.extend(["--author", f"{author} <{email}>"])
        code, out, err = await self._run_git(*args)
        return {"success": code == 0, "output": out, "error": err if code != 0 else ""}

    async def get_log(self, count: int = 50) -> dict[str, Any]:
        """Get commit log."""
        fmt = "%H|%h|%an|%ad|%s"
        code, out, _ = await self._run_git(
            "log", f"-{count}", f"--pretty=format:{fmt}", "--date=short"
        )
        if code != 0:
            return {"commits": []}

        commits: list[dict[str, Any]] = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) < 5:
                continue
            commits.append({
                "hash": parts[0],
                "shortHash": parts[1],
                "author": parts[2],
                "date": parts[3],
                "message": parts[4],
            })

        return {"commits": commits}

    async def get_branches(self) -> dict[str, Any]:
        """Get all branches."""
        code, out, _ = await self._run_git("branch", "--list", "--all", "-v")
        if code != 0:
            return {"branches": []}

        branches: list[dict[str, Any]] = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            current = line.startswith("*")
            line = line.lstrip("* ").strip()
            parts = line.split(None, 1)
            if not parts:
                continue
            name = parts[0]
            last_commit = parts[1] if len(parts) > 1 else ""
            remote = name.startswith("remotes/")
            branches.append({
                "name": name,
                "current": current,
                "remote": remote,
                "lastCommit": last_commit,
            })

        return {"branches": branches}

    async def checkout_branch(self, name: str) -> dict[str, Any]:
        """Checkout a branch."""
        code, out, err = await self._run_git("checkout", name)
        return {"success": code == 0, "output": out, "error": err if code != 0 else ""}

    async def create_branch(self, name: str) -> dict[str, Any]:
        """Create a new branch."""
        code, out, err = await self._run_git("checkout", "-b", name)
        return {"success": code == 0, "output": out, "error": err if code != 0 else ""}

    async def discard_changes(self, path: str) -> dict[str, Any]:
        """Discard changes to a file."""
        code, _, err = await self._run_git("checkout", "--", path)
        return {"success": code == 0, "error": err if code != 0 else ""}

    async def search_files(self, query: str, file_pattern: str = "") -> dict[str, Any]:
        """Search file contents using grep (ripgrep fallback)."""
        args = ["grep", "-n", "-i", "--line-number"]
        if file_pattern:
            args.extend(["--", file_pattern, query])
        else:
            args.extend(["--", query])

        code, out, _ = await self._run_git(*args)
        if code != 0:
            # Fallback to system grep
            full_path = Path(self.working_dir)
            proc = await asyncio.create_subprocess_exec(
                "grep", "-rn", "-i", query, ".",
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            out = stdout.decode("utf-8", errors="replace")

        results: list[dict[str, Any]] = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            # Parse path:line:content
            parts = line.split(":", 2)
            if len(parts) >= 3:
                results.append({
                    "path": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                    "content": parts[2],
                })

        return {"results": results, "query": query}
