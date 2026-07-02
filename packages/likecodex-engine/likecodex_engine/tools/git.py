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
                    "use_ai": {"type": "boolean", "default": False, "description": "Use AI to generate commit message"},
                },
                "required": [],
            },
        }

    async def _generate_ai_commit_message(self) -> str:
        """Generate a commit message using AI analysis of the staged diff.

        Analyzes the diff content and file changes to create a structured message.
        Falls back to regular generation if AI is unavailable.
        """
        # Get diff content for analysis
        diff_result = await self._run("diff --cached")
        stat_result = await self._run("diff --cached --stat")

        diff_content = diff_result.get("stdout", "")[:2000]
        stat_content = stat_result.get("stdout", "") or ""

        if not diff_content and not stat_content:
            return "Auto-commit: no staged changes"

        # Extract changed file extensions for type detection
        changed_exts = set()
        changed_keywords = []
        for line in stat_content.split("\n"):
            if "|" in line:
                fname = line.split("|")[0].strip()
                ext = Path(fname).suffix.lower()
                if ext:
                    changed_exts.add(ext)
                changed_keywords.append(fname)

        # Smart type detection
        type_map = {
            ".py": "feat", ".rs": "feat", ".js": "feat", ".ts": "feat",
            ".jsx": "feat", ".tsx": "feat", ".go": "feat", ".java": "feat",
            ".md": "docs", ".rst": "docs", ".txt": "docs",
            ".css": "style", ".scss": "style", ".less": "style",
            ".json": "chore", ".yaml": "chore", ".yml": "chore", ".toml": "chore",
        }

        commit_type = "chore"
        type_priority = {"feat": 0, "fix": 1, "docs": 2, "test": 3, "style": 4, "chore": 5}
        for fname in changed_keywords:
            lower = fname.lower()
            if any(k in lower for k in ["test_", "_test", ".spec.", ".test."]):
                if type_priority.get("test", 99) < type_priority.get(commit_type, 99):
                    commit_type = "test"
            if any(k in lower for k in ["fix", "bug", "hotfix", "issue"]):
                if type_priority.get("fix", 99) < type_priority.get(commit_type, 99):
                    commit_type = "fix"

        # Determine type from extensions (lower priority)
        for ext in changed_exts:
            detected = type_map.get(ext)
            if detected and type_priority.get(detected, 99) < type_priority.get(commit_type, 99):
                commit_type = detected

        # Infer scope from directory structure
        scopes = set()
        for fname in changed_keywords:
            parts = fname.replace("\\", "/").split("/")
            if len(parts) >= 2:
                scopes.add(parts[0])
            if len(parts) >= 3:
                scopes.add(f"{parts[0]}/{parts[1]}")

        scope_str = f"({', '.join(sorted(scopes)[:2])})" if scopes else ""

        # Generate description from first meaningful file name
        file_count = len(changed_keywords)
        first_name = Path(changed_keywords[0]).stem.replace("_", " ").replace("-", " ") if changed_keywords else "changes"

        if file_count == 1:
            desc = first_name[:70]
        elif file_count <= 3:
            names = [Path(f).stem.replace("_", " ").replace("-", " ")[:20] for f in changed_keywords]
            desc = ', '.join(names)
        else:
            desc = f"{first_name[:35]} +{file_count - 1} more"

        # Add diff summary for more context
        additions = diff_content.count("\n+") - diff_content.count("\n+++")
        deletions = diff_content.count("\n-") - diff_content.count("\n---")
        if additions > 0 or deletions > 0:
            desc += f" ({'+' if additions > 0 else ''}{additions}/-{deletions})"

        message = f"{commit_type}{scope_str}: {desc}"
        return message[:120]

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

    async def git_commit(self, message: str = "", add_all: bool = True, auto_message: bool = True, use_ai: bool = False) -> str:
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
            if use_ai:
                message = await self._generate_ai_commit_message()
            else:
                message = await self._generate_commit_message()

        if not message:
            message = "Auto-commit"

        escaped_message = message.replace('"', '\\"')
        result = await self._run(f'commit -m "{escaped_message}"')
        return json.dumps(result)

    def stash_schema(self) -> dict[str, Any]:
        return {
            "description": "Manage git stash (push, pop, list, drop, apply).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["push", "pop", "list", "drop", "apply"],
                        "description": "Stash action to perform",
                    },
                    "message": {
                        "type": "string",
                        "description": "Stash message (for push action)",
                    },
                    "stash_ref": {
                        "type": "string",
                        "description": "Stash reference like stash@{0} (for pop/drop/apply)",
                    },
                },
                "required": ["action"],
            },
        }

    async def git_stash(self, action: str = "list", message: str = "", stash_ref: str = "") -> str:
        """Manage git stash (push, pop, list, drop, apply)."""
        if action == "push":
            if message:
                result = await self._run(f'stash push -m "{message.replace(chr(34), chr(92)+chr(34))}"')
            else:
                result = await self._run("stash push")
        elif action == "pop":
            result = await self._run(f"stash pop {stash_ref}" if stash_ref else "stash pop")
        elif action == "apply":
            result = await self._run(f"stash apply {stash_ref}" if stash_ref else "stash apply")
        elif action == "drop":
            result = await self._run(f"stash drop {stash_ref}" if stash_ref else "stash drop")
        else:
            result = await self._run("stash list")
        return json.dumps(result)

    def rebase_schema(self) -> dict[str, Any]:
        return {
            "description": "Perform git rebase operations (interactive, abort, continue).",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target branch/ref to rebase onto (default: main)",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["start", "continue", "abort", "skip"],
                        "description": "Rebase action",
                    },
                    "interactive": {
                        "type": "boolean",
                        "description": "Use interactive rebase",
                    },
                },
                "required": [],
            },
        }

    async def git_rebase(self, target: str = "main", action: str = "start", interactive: bool = False) -> str:
        """Perform git rebase operations."""
        if action == "continue":
            result = await self._run("rebase --continue")
        elif action == "abort":
            result = await self._run("rebase --abort")
        elif action == "skip":
            result = await self._run("rebase --skip")
        else:
            # Auto-detect default branch
            resolved_target = target
            if target == "main":
                branch_check = await self._run("rev-parse --verify main")
                if branch_check.get("exit_code") != 0:
                    resolved_target = "master"

            if interactive:
                result = await self._run(f"rebase -i {resolved_target}")
            else:
                result = await self._run(f"rebase {resolved_target}")
        return json.dumps(result)

    def resolve_conflict_schema(self) -> dict[str, Any]:
        return {
            "description": "List conflicted files and help resolve merge/rebase conflicts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "status", "ours", "theirs", "both"],
                        "description": "Action to perform on conflicts",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "File path to resolve (required for ours/theirs/both)",
                    },
                },
                "required": [],
            },
        }

    async def git_resolve_conflict(self, action: str = "list", file_path: str = "") -> str:
        """List conflicted files and help resolve merge/rebase conflicts."""
        if action == "list" or action == "status":
            # Show conflicted files
            result = await self._run("diff --name-only --diff-filter=U")
            if result.get("exit_code") == 0 and result.get("stdout", "").strip():
                conflict_files = [f for f in result["stdout"].strip().split("\n") if f.strip()]
                # Also check merge conflicts via status
                status_result = await self._run("status --porcelain")
                merge_conflicts = []
                if status_result.get("stdout"):
                    for line in status_result["stdout"].strip().split("\n"):
                        if line.startswith("UU") or line.startswith("AA") or line.startswith("DD"):
                            merge_conflicts.append(line[3:].strip())
                return json.dumps({
                    "conflicted_files": list(set(conflict_files + merge_conflicts)),
                    "has_conflicts": len(conflict_files) + len(merge_conflicts) > 0,
                })
            return json.dumps({"conflicted_files": [], "has_conflicts": False})

        if not file_path:
            return json.dumps({"error": "file_path is required for resolution actions"})

        if action == "ours":
            result = await self._run(f"checkout --ours {file_path}")
            if result.get("exit_code") == 0:
                await self._run(f"add {file_path}")
            return json.dumps({**result, "resolution": f"Kept our version of {file_path}", "file": file_path})
        elif action == "theirs":
            result = await self._run(f"checkout --theirs {file_path}")
            if result.get("exit_code") == 0:
                await self._run(f"add {file_path}")
            return json.dumps({**result, "resolution": f"Kept their version of {file_path}", "file": file_path})

        return json.dumps({"error": f"Unknown action: {action}"})

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

    # ============================================================
    # Phase 3.6: Composer Batch Commit
    # ============================================================

    def composer_commit_schema(self) -> dict[str, Any]:
        return {
            "description": "Batch commit file changes grouped by feature/component.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "change_type": {
                                    "type": "string",
                                    "enum": ["create", "modify", "delete"],
                                },
                                "description": {"type": "string"},
                            },
                            "required": ["path"],
                        },
                        "description": "List of file changes to commit",
                    },
                    "group_by": {
                        "type": "string",
                        "enum": ["component", "directory", "none"],
                        "default": "component",
                        "description": "How to group changes",
                    },
                    "message": {
                        "type": "string",
                        "description": "Optional override commit message",
                    },
                },
                "required": ["file_changes"],
            },
        }

    async def composer_commit(
        self,
        file_changes: list[dict[str, Any]],
        group_by: str = "component",
        message: str = "",
    ) -> str:
        """Batch commit file changes grouped by feature/component.

        Args:
            file_changes: List of dicts with 'path' and optionally 'change_type' and 'description'.
            group_by: How to group ('component', 'directory', 'none').
            message: Optional override message.

        Returns:
            JSON with commit results.
        """
        if not file_changes:
            return json.dumps({"error": "No file changes provided"})

        if message:
            # Single commit with custom message
            return await self._do_atomic_commit(file_changes, message)

        # Group changes
        if group_by == "none":
            groups = {"changes": file_changes}
        else:
            groups = self._group_file_changes(file_changes, group_by)

        results: list[dict[str, Any]] = []
        for group_name, group_files in groups.items():
            auto_msg = self._generate_composer_message(group_name, group_files)
            result = await self._do_atomic_commit(group_files, auto_msg)
            results.append(json.loads(result))

        return json.dumps({
            "commits": results,
            "total": len(results),
            "files": len(file_changes),
        }, ensure_ascii=False)

    def _group_file_changes(
        self,
        file_changes: list[dict[str, Any]],
        group_by: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """Group file changes by component or directory."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for fc in file_changes:
            path = fc.get("path", "")
            if group_by == "component":
                # Try to extract component: e.g. "composer/manager.py" -> "composer"
                parts = path.replace("\\", "/").split("/")
                key = parts[0] if len(parts) > 1 else "root"
            elif group_by == "directory":
                path_obj = Path(path)
                key = str(path_obj.parent) if path_obj.parent != Path(".") else "root"
            else:
                key = "changes"

            # Normalize key
            key = key.replace("\\", "/").strip("/") or "root"
            if key not in groups:
                groups[key] = []
            groups[key].append(fc)
        return groups

    @staticmethod
    def _generate_composer_message(
        group_name: str,
        group_files: list[dict[str, Any]],
    ) -> str:
        """Generate an auto-commit message for a group of file changes."""
        # Detect change types
        has_create = any(fc.get("change_type") == "create" for fc in group_files)
        has_modify = any(fc.get("change_type") == "modify" for fc in group_files)
        has_delete = any(fc.get("change_type") == "delete" for fc in group_files)

        change_words = []
        if has_create:
            change_words.append("Add")
        if has_modify:
            change_words.append("Update")
        if has_delete:
            change_words.append("Remove")

        action = " / ".join(change_words) if change_words else "Update"

        # Collect descriptions
        descriptions = [
            fc.get("description", Path(fc["path"]).name)
            for fc in group_files
            if fc.get("description")
        ]

        file_count = len(group_files)
        if descriptions:
            detail = "; ".join(descriptions[:5])
            if len(descriptions) > 5:
                detail += f" +{len(descriptions) - 5} more"
        else:
            detail = f"{file_count} file(s)"

        return f"{action} {group_name}: {detail}"[:100]

    async def _do_atomic_commit(
        self,
        file_changes: list[dict[str, Any]],
        commit_message: str,
    ) -> str:
        """Stage specific files and commit atomically."""
        # Stage only the specific files
        for fc in file_changes:
            path = fc.get("path", "")
            if path:
                await self._run(f'add "{path}"')

        # Check if there's anything to commit
        status_result = await self._run("status --porcelain")
        if not status_result.get("stdout", "").strip():
            return json.dumps({
                "message": commit_message,
                "skip": True,
                "reason": "Nothing to commit",
            })

        escaped = commit_message.replace('"', '\\"')
        result = await self._run(f'commit -m "{escaped}"')

        return json.dumps({
            "message": commit_message,
            "files": [fc.get("path", "") for fc in file_changes],
            "file_count": len(file_changes),
            **result,
        }, ensure_ascii=False)
