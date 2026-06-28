"""SEARCH/REPLACE file editing tool."""

from __future__ import annotations

import json
import re
from difflib import unified_diff
from pathlib import Path
from typing import Any

from likecodex_engine.tools.encoding import read_text_detect, write_text_preserve
from likecodex_engine.tools.path_utils import resolve_in_working_dir


class EditFileTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = working_dir

    def _resolve_file(self, path: str) -> tuple[Path | None, str | None]:
        """Resolve a file path, returning (path, None) on success or (None, error_json) on failure."""
        try:
            return resolve_in_working_dir(Path(self.working_dir), path), None
        except PermissionError as exc:
            return None, json.dumps({"error": str(exc)})

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
        target, err = self._resolve_file(path)
        if err:
            return err

        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})

        decoded = read_text_detect(target)
        before = decoded.text
        if old_string not in before:
            hint = self._context_hint(before, old_string)
            return json.dumps({"error": f"old_string not found in {path}", "hint": hint})

        if replace_all:
            after = before.replace(old_string, new_string)
            count = before.count(old_string)
        else:
            after = before.replace(old_string, new_string, 1)
            count = 1

        used = write_text_preserve(target, after, decoded.encoding)
        return json.dumps(
            {
                "path": path,
                "replacements": count,
                "diff": self._diff(path, before, after),
                "before_len": len(before),
                "after_len": len(after),
                "encoding": used,
            }
        )

    def multi_edit_schema(self) -> dict[str, Any]:
        return {
            "description": "Apply multiple SEARCH/REPLACE edits to one file atomically (all or nothing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "edits": {
                        "type": "array",
                        "description": "List of edits applied in order",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_string": {"type": "string"},
                                "new_string": {"type": "string"},
                                "replace_all": {"type": "boolean", "default": False},
                            },
                            "required": ["old_string", "new_string"],
                        },
                    },
                },
                "required": ["path", "edits"],
            },
        }

    async def multi_edit(self, path: str, edits: list[dict[str, Any]]) -> str:
        target, err = self._resolve_file(path)
        if err:
            return err
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if not edits:
            return json.dumps({"error": "No edits provided"})

        decoded = read_text_detect(target)
        before = decoded.text
        current = before
        total = 0
        for i, edit in enumerate(edits):
            old = edit.get("old_string", "")
            new = edit.get("new_string", "")
            replace_all = bool(edit.get("replace_all", False))
            if old not in current:
                return json.dumps(
                    {
                        "error": f"edit #{i + 1} old_string not found in {path}",
                        "hint": self._context_hint(current, old),
                    }
                )
            if replace_all:
                total += current.count(old)
                current = current.replace(old, new)
            else:
                total += 1
                current = current.replace(old, new, 1)

        used = write_text_preserve(target, current, decoded.encoding)
        return json.dumps(
            {
                "path": path,
                "edits_applied": len(edits),
                "replacements": total,
                "diff": self._diff(path, before, current),
                "encoding": used,
            }
        )

    def delete_range_schema(self) -> dict[str, Any]:
        return {
            "description": "Delete an inclusive 1-indexed line range from a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "description": "First line to delete (1-indexed)"},
                    "end_line": {"type": "integer", "description": "Last line to delete (inclusive)"},
                },
                "required": ["path", "start_line", "end_line"],
            },
        }

    async def delete_range(self, path: str, start_line: int, end_line: int) -> str:
        target, err = self._resolve_file(path)
        if err:
            return err
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if start_line < 1 or end_line < start_line:
            return json.dumps({"error": f"Invalid range: {start_line}-{end_line}"})

        decoded = read_text_detect(target)
        before = decoded.text
        lines = before.splitlines(keepends=True)
        if start_line > len(lines):
            return json.dumps({"error": f"start_line {start_line} beyond end of file ({len(lines)} lines)"})
        end = min(end_line, len(lines))
        after = "".join(lines[: start_line - 1] + lines[end:])
        used = write_text_preserve(target, after, decoded.encoding)
        return json.dumps(
            {
                "path": path,
                "deleted_lines": end - start_line + 1,
                "diff": self._diff(path, before, after),
                "encoding": used,
            }
        )

    def delete_symbol_schema(self) -> dict[str, Any]:
        return {
            "description": "Delete a top-level or indented symbol block (def/class/function) by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "name": {"type": "string", "description": "Symbol name to remove"},
                },
                "required": ["path", "name"],
            },
        }

    async def delete_symbol(self, path: str, name: str) -> str:
        target, err = self._resolve_file(path)
        if err:
            return err
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})

        decoded = read_text_detect(target)
        before = decoded.text
        lines = before.splitlines(keepends=True)
        # Match common definition forms across Python / JS / TS / Go / Rust.
        pattern = re.compile(
            rf"^(\s*)"
            rf"(?:export\s+|public\s+|private\s+|async\s+|pub\s+)*"
            rf"(?:def|class|function|func|fn|interface|struct|type|const|let|var)\s+"
            rf"{re.escape(name)}\b"
        )
        start_idx = None
        indent = ""
        for i, line in enumerate(lines):
            m = pattern.match(line)
            if m:
                start_idx = i
                indent = m.group(1)
                break
        if start_idx is None:
            return json.dumps({"error": f"Symbol '{name}' not found in {path}"})

        end_idx = self._symbol_block_end(lines, start_idx, indent)
        after = "".join(lines[:start_idx] + lines[end_idx:])
        used = write_text_preserve(target, after, decoded.encoding)
        return json.dumps(
            {
                "path": path,
                "symbol": name,
                "deleted_lines": end_idx - start_idx,
                "diff": self._diff(path, before, after),
                "encoding": used,
            }
        )

    @staticmethod
    def _symbol_block_end(lines: list[str], start_idx: int, indent: str) -> int:
        """Find the end (exclusive) of an indentation-delimited symbol block."""
        n = len(lines)
        brace_depth = lines[start_idx].count("{") - lines[start_idx].count("}")
        if brace_depth > 0:
            # Brace-delimited languages: consume until braces balance.
            i = start_idx + 1
            while i < n and brace_depth > 0:
                brace_depth += lines[i].count("{") - lines[i].count("}")
                i += 1
            return i
        # Indentation-delimited (Python-like): consume more-indented lines.
        i = start_idx + 1
        while i < n:
            line = lines[i]
            if line.strip() == "":
                i += 1
                continue
            cur_indent = line[: len(line) - len(line.lstrip())]
            if len(cur_indent) <= len(indent):
                break
            i += 1
        return i

    def _diff(self, path: str, before: str, after: str) -> str:
        return "\n".join(
            unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
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
