"""SEARCH/REPLACE file editing tool."""

from __future__ import annotations

import json
from difflib import unified_diff
from pathlib import Path

from likecodex_engine.tools.path_utils import resolve_in_working_dir


class EditFileTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = working_dir

    def edit_file_schema(self) -> dict:
        return {
            "description": "Replace old_string with new_string in a file. Prefer over write_file for edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "old_string": {"type": "string", "description": "Exact text to replace"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences",
                        "default": False,
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        }

    async def edit_file(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        try:
            target = resolve_in_working_dir(Path(self.working_dir), path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc)})

        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})

        before = target.read_text(encoding="utf-8")
        if old_string not in before:
            hint = self._context_hint(before, old_string)
            return json.dumps({"error": f"old_string not found in {path}", "hint": hint})

        if replace_all:
            after = before.replace(old_string, new_string)
            count = before.count(old_string)
        else:
            after = before.replace(old_string, new_string, 1)
            count = 1

        target.write_text(after, encoding="utf-8")
        diff = "\n".join(
            unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        return json.dumps(
            {
                "path": path,
                "replacements": count,
                "diff": diff,
                "before_len": len(before),
                "after_len": len(after),
            }
        )

    def _context_hint(self, content: str, needle: str) -> str:
        """Provide nearby lines when exact match fails."""
        lines = content.splitlines()
        needle_words = needle.split()[:3]
        for i, line in enumerate(lines):
            if any(w in line for w in needle_words if w):
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                snippet = "\n".join(f"{j + 1}: {lines[j]}" for j in range(start, end))
                return f"Near line {i + 1}:\n{snippet}"
        return "No similar context found."
