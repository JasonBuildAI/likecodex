"""SEARCH/REPLACE file editing tool."""

from __future__ import annotations

import json
import re
from difflib import unified_diff
from pathlib import Path
from typing import Any

from likecodex_engine.tools.encoding import read_text_detect, write_text_preserve
from likecodex_engine.tools.path_utils import resolve_in_working_dir
from likecodex_engine.tools.undo_stack import EditEntry, UndoStack


class EditFileTools:
    def __init__(self, working_dir: str, undo_stack: UndoStack | None = None) -> None:
        self.working_dir = working_dir
        self.undo_stack = undo_stack or UndoStack(max_depth=50)

    def _resolve_file(self, path: str) -> tuple[Path | None, str | None]:
        """Resolve a file path, returning (path, None) on success or (None, error_json) on failure."""
        try:
            return resolve_in_working_dir(Path(self.working_dir), path), None
        except PermissionError as exc:
            return None, json.dumps({"error": str(exc)})

    def edit_file_schema(self) -> dict:
        return {
            "description": "Edit a file. Supports three modes: search_replace (default), patch (git diff patch), replace (full file).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "old_string": {"type": "string", "description": "Exact text to replace (search_replace mode)"},
                    "new_string": {"type": "string", "description": "Replacement text (search_replace mode)"},
                    "patch": {"type": "string", "description": "Git unified diff patch to apply (patch mode)"},
                    "mode": {
                        "type": "string",
                        "enum": ["search_replace", "patch", "replace"],
                        "description": "Edit mode: search_replace (old→new), patch (git diff), replace (full content via content param)",
                        "default": "search_replace",
                    },
                    "content": {"type": "string", "description": "Full file content (replace mode only)"},
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (search_replace mode)",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        }

    async def edit_file(
        self,
        path: str,
        old_string: str = "",
        new_string: str = "",
        replace_all: bool = False,
        mode: str = "search_replace",
        content: str = "",
        patch: str = "",
    ) -> str:
        """Edit a file in one of three modes (Phase 3.11).

        Modes:
        - search_replace (default): Replace old_string with new_string (incremental).
        - replace: Overwrite entire file with content (full replacement).
        - patch: Apply a git unified diff patch string.
        """
        target, err = self._resolve_file(path)
        if err:
            return err

        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})

        decoded = read_text_detect(target)
        before = decoded.text

        if mode == "replace":
            # Phase 3.11: 全量替换模式 — 用 content 完全覆盖文件
            if not content:
                return json.dumps({"error": "'content' required for replace mode"})
            after = content
            mode_label = "replace"

        elif mode == "patch":
            # Phase 3.11: Patch 模式 — 应用 git unified diff
            if not patch:
                return json.dumps({"error": "'patch' required for patch mode"})
            after = self._apply_patch(before, patch)
            if after is None:
                return json.dumps({"error": f"Failed to apply patch to {path}: hunk(s) did not match"})
            mode_label = "patch"

        else:
            # search_replace (default) — 增量编辑
            if not old_string:
                return json.dumps({"error": "'old_string' required for search_replace mode"})
            if old_string not in before:
                hint = self._context_hint(before, old_string)
                return json.dumps({"error": f"old_string not found in {path}", "hint": hint})
            if replace_all:
                after = before.replace(old_string, new_string)
                count = before.count(old_string)
            else:
                after = before.replace(old_string, new_string, 1)
                count = 1
            mode_label = f"search_replace ({count} replacement(s))"

        if after == before:
            return json.dumps({"path": path, "mode": mode, "no_change": True})

        used = write_text_preserve(target, after, decoded.encoding)

        # Track in undo stack
        self.undo_stack.push(path, before, after, description=mode_label)

        return json.dumps(
            {
                "path": path,
                "mode": mode_label,
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

        # Track whole group in undo stack
        entries = [
            EditEntry(
                file_path=path,
                before_content=before,
                after_content=current,
                description=f"multi_edit #{len(edits)}",
            )
        ]
        self.undo_stack.push_group(entries, description=f"multi_edit({len(edits)} edits)")

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

    # ============================================================
    # Phase 3.11: Patch 模式 — git unified diff 解析与应用
    # ============================================================

    @staticmethod
    def _apply_patch(original: str, patch_text: str) -> str | None:
        """Apply a git unified diff patch to the original content.

        Parses hunks like:
            @@ -start,count +start,count @@
            -old_line
            +new_line

        Hunks are applied from bottom to top so line numbers stay valid.
        Returns the patched content, or None if any hunk fails to match.
        """
        lines = original.splitlines(keepends=True)
        hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

        # Phase 1: parse all hunks
        raw_hunks = patch_text.split("\n@@ ")
        parsed_hunks: list[tuple[int, int, list[str], list[str]]] = []

        for raw in raw_hunks:
            if not raw.strip():
                continue
            # Re-prepend @@ if we split on it
            hunk_str = raw if raw.startswith("@@") else "@@ " + raw
            hunk_lines = hunk_str.splitlines(keepends=True)
            if not hunk_lines:
                continue

            header_match = hunk_re.match(hunk_lines[0].strip())
            if not header_match:
                continue

            old_start = int(header_match.group(1))
            # new_start = int(header_match.group(3))

            old_hunk: list[str] = []
            new_hunk: list[str] = []

            for hl in hunk_lines[1:]:
                if hl.startswith("-"):
                    old_hunk.append(hl[1:])
                elif hl.startswith("+"):
                    new_hunk.append(hl[1:])
                else:
                    stripped = hl[1:] if hl.startswith(" ") else hl
                    old_hunk.append(stripped)
                    new_hunk.append(stripped)

            parsed_hunks.append((old_start, len(old_hunk), old_hunk, new_hunk))

        # Phase 2: apply from bottom to top
        result = list(lines)
        for old_start, _old_count, old_hunk, new_hunk in sorted(parsed_hunks, key=lambda x: -x[0]):
            old_slice_start = old_start - 1  # convert to 0-indexed
            old_slice_end = old_slice_start + len(old_hunk)

            if result[old_slice_start:old_slice_end] != old_hunk:
                return None

            result = result[:old_slice_start] + new_hunk + result[old_slice_end:]

        return "".join(result)

    # ============================================================
    # Phase 3.5: Undo/Redo Convenience Methods
    # ============================================================

    def undo_schema(self) -> dict[str, Any]:
        return {
            "description": "Undo the last file edit.",
            "parameters": {"type": "object", "properties": {}},
        }

    async def undo(self) -> str:
        """Undo the last edit group."""
        group = self.undo_stack.undo()
        if group is None:
            return json.dumps({"error": "Nothing to undo"})
        restored = []
        for entry in group.edits:
            target, err = self._resolve_file(entry.file_path)
            if err:
                continue
            if target and target.exists():
                decoded = read_text_detect(target)
                write_text_preserve(target, entry.before_content, decoded.encoding)
                restored.append(entry.file_path)
        return json.dumps({
            "undone": True,
            "files": restored,
            "description": group.description,
        })

    def redo_schema(self) -> dict[str, Any]:
        return {
            "description": "Redo the last undone edit.",
            "parameters": {"type": "object", "properties": {}},
        }

    async def redo(self) -> str:
        """Redo the last undone edit group."""
        group = self.undo_stack.redo()
        if group is None:
            return json.dumps({"error": "Nothing to redo"})
        restored = []
        for entry in group.edits:
            target, err = self._resolve_file(entry.file_path)
            if err:
                continue
            if target and target.exists():
                decoded = read_text_detect(target)
                write_text_preserve(target, entry.after_content, decoded.encoding)
                restored.append(entry.file_path)
        return json.dumps({
            "redone": True,
            "files": restored,
            "description": group.description,
        })

    def undo_history_schema(self) -> dict[str, Any]:
        return {
            "description": "Get undo/redo history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "Max entries to return",
                    }
                },
            },
        }

    async def undo_history(self, limit: int = 20) -> str:
        """Get recent undo history."""
        history = self.undo_stack.get_undo_history(limit=limit)
        return json.dumps({
            "history": history,
            "can_undo": self.undo_stack.can_undo(),
            "can_redo": self.undo_stack.can_redo(),
            "undo_count": self.undo_stack.undo_count,
            "redo_count": self.undo_stack.redo_count,
        })
