"""Filesystem tools for the agent."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from likecodex_engine.tools.encoding import read_text_detect, write_text_preserve
from likecodex_engine.tools.path_utils import (
    MAX_READ_BYTES,
    SKIP_DIRS,
    resolve_in_working_dir,
    should_skip_path,
)


class FileSystemTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    def _resolve(self, path: str) -> Path:
        return resolve_in_working_dir(self.working_dir, path)

    def _safe_resolve(self, path: str) -> tuple[Path | None, str | None]:
        """Resolve a path, returning (path, None) on success or (None, error_json) on failure."""
        try:
            return self._resolve(path), None
        except PermissionError as exc:
            return None, json.dumps({"error": str(exc)})

    def read_file_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Read a text file with optional line offset/limit. Lines are prefixed "
                "with 1-based numbers (e.g. `   42→...`) for edit targeting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path within the workspace"},
                    "offset": {"type": "integer", "description": "1-based start line", "default": 1},
                    "limit": {"type": "integer", "description": "Max lines to read"},
                },
                "required": ["path"],
            },
        }

    async def read_file(self, path: str, offset: int = 1, limit: int | None = None) -> str:
        target, err = self._safe_resolve(path)
        if err:
            return err
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if not target.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        size = target.stat().st_size
        if size > MAX_READ_BYTES and limit is None:
            limit = 200
        decoded = read_text_detect(target)
        lines = decoded.text.splitlines()
        total = len(lines)
        start = max(1, offset) - 1
        end = total if limit is None else min(total, start + limit)
        window = lines[start:end]
        numbered = "\n".join(f"{start + i + 1:5d}→{line}" for i, line in enumerate(window))
        trailer = f"\n\n[total_lines={total}, showing {start + 1}-{end}]"
        if end < total:
            trailer += f" Use offset={end + 1} to read more."
        return json.dumps(
            {
                "path": str(target.relative_to(self.working_dir)),
                "content": numbered + trailer,
                "encoding": decoded.encoding,
                "total_lines": total,
            }
        )

    def write_file_schema(self) -> dict[str, Any]:
        return {
            "description": "Write content to a file, creating parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        }

    async def write_file(self, path: str, content: str) -> str:
        target, err = self._safe_resolve(path)
        if err:
            return err
        target.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the existing file's encoding so we don't silently convert
        # GBK/UTF-16 files to UTF-8 on overwrite.
        encoding = "utf-8"
        if target.exists() and target.is_file():
            try:
                encoding = read_text_detect(target).encoding
            except OSError:
                encoding = "utf-8"
        used = write_text_preserve(target, content, encoding)
        return json.dumps(
            {
                "path": str(target.relative_to(self.working_dir)),
                "written": True,
                "bytes": len(content),
                "encoding": used,
            }
        )

    def move_file_schema(self) -> dict[str, Any]:
        return {
            "description": "Move or rename a file or directory within the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Existing relative path"},
                    "destination": {"type": "string", "description": "Target relative path"},
                    "overwrite": {
                        "type": "boolean",
                        "description": "Overwrite destination if it exists",
                        "default": False,
                    },
                },
                "required": ["source", "destination"],
            },
        }

    async def move_file(self, source: str, destination: str, overwrite: bool = False) -> str:
        src, err = self._safe_resolve(source)
        if err:
            return err
        dst, err = self._safe_resolve(destination)
        if err:
            return err
        if not src.exists():
            return json.dumps({"error": f"Source not found: {source}"})
        if dst.exists() and not overwrite:
            return json.dumps({"error": f"Destination exists: {destination} (set overwrite=true)"})
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and overwrite:
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        src.replace(dst)
        return json.dumps(
            {
                "moved": True,
                "source": str(src.relative_to(self.working_dir)),
                "destination": str(dst.relative_to(self.working_dir)),
            }
        )

    def glob_schema(self) -> dict[str, Any]:
        return {
            "description": "Find files matching a glob pattern (e.g. 'src/**/*.py').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern relative to workspace"},
                    "max_results": {"type": "integer", "default": 200},
                },
                "required": ["pattern"],
            },
        }

    async def glob(self, pattern: str, max_results: int = 200) -> str:
        glob_pattern = pattern
        if "*" in glob_pattern and "**" not in glob_pattern and "/" not in glob_pattern:
            glob_pattern = f"**/{glob_pattern}"
        matches: list[dict[str, Any]] = []
        for entry in self.working_dir.glob(glob_pattern):
            if should_skip_path(self.working_dir, entry):
                continue
            try:
                rel = entry.relative_to(self.working_dir)
            except ValueError:
                continue
            matches.append(
                {
                    "path": str(rel),
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else None,
                }
            )
            if len(matches) >= max_results:
                break
        # Stable order so cache/output stays deterministic.
        matches.sort(key=lambda m: m["path"])
        return json.dumps({"pattern": pattern, "matches": matches, "count": len(matches)})

    def ls_schema(self) -> dict[str, Any]:
        return {
            "description": "List directory entries, optionally recursive, with skip-dir filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "recursive": {"type": "boolean", "default": False},
                    "max_entries": {"type": "integer", "default": 200},
                },
            },
        }

    async def ls(self, path: str = ".", recursive: bool = False, max_entries: int = 200) -> str:
        target, err = self._safe_resolve(path)
        if err:
            return err
        if not target.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        if not target.is_dir():
            return json.dumps({"error": f"Not a directory: {path}"})
        entries: list[dict[str, Any]] = []
        if recursive:
            for root, dirs, files in os.walk(target):
                root_path = Path(root)
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in sorted(dirs) + sorted(files):
                    entry = root_path / name
                    if should_skip_path(self.working_dir, entry):
                        continue
                    entries.append(self._entry_info(entry))
                    if len(entries) >= max_entries:
                        break
                if len(entries) >= max_entries:
                    break
        else:
            for entry in sorted(target.iterdir(), key=lambda p: p.name):
                if entry.name in SKIP_DIRS:
                    continue
                entries.append(self._entry_info(entry))
                if len(entries) >= max_entries:
                    break
        return json.dumps(
            {
                "path": str(target.relative_to(self.working_dir)),
                "recursive": recursive,
                "entries": entries,
                "count": len(entries),
            }
        )

    def _entry_info(self, entry: Path) -> dict[str, Any]:
        return {
            "path": str(entry.relative_to(self.working_dir)),
            "name": entry.name,
            "type": "directory" if entry.is_dir() else "file",
            "size": entry.stat().st_size if entry.is_file() else None,
        }

    def list_dir_schema(self) -> dict[str, Any]:
        return {
            "description": "List files and directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
            },
        }

    async def list_dir(self, path: str = ".") -> str:
        """Simple directory listing — delegates to ls with sane defaults."""
        return await self.ls(path, recursive=False, max_entries=1000)

    def search_files_schema(self) -> dict[str, Any]:
        return {
            "description": "Search file contents for a regex pattern with enhanced filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "description": "Directory to search in, relative to workspace"},
                    "glob": {"type": "string", "description": "Optional file glob pattern, e.g. '*.py' or 'src/**/*.ts'"},
                    "case_insensitive": {"type": "boolean", "default": False},
                    "max_results": {"type": "integer", "default": 50},
                    "context_lines": {"type": "integer", "default": 0, "description": "Lines of context before/after each match"},
                    "max_file_size_kb": {"type": "integer", "default": 1024, "description": "Skip files larger than this (KB)"},
                },
                "required": ["pattern"],
            },
        }

    async def search_files(self, pattern: str, path: str = ".", glob: str | None = None,
                            case_insensitive: bool = False, max_results: int = 50,
                            context_lines: int = 0, max_file_size_kb: int = 1024) -> str:
        target, err = self._safe_resolve(path)
        if err:
            return err
        results = []
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)
        max_bytes = max_file_size_kb * 1024

        # Use glob if provided, otherwise walk
        if glob:
            search_root = self.working_dir if str(target) == str(self.working_dir) else target
            for entry in search_root.glob(glob):
                if not entry.is_file() or should_skip_path(self.working_dir, entry):
                    continue
                if entry.stat().st_size > max_bytes:
                    continue
                results = await self._search_in_file(entry, regex, context_lines, results, max_results)
                if len(results) >= max_results:
                    break
        else:
            for root, dirs, files in os.walk(target):
                root_path = Path(root)
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                if should_skip_path(self.working_dir, root_path):
                    continue
                for name in files:
                    filepath = root_path / name
                    if should_skip_path(self.working_dir, filepath):
                        continue
                    if filepath.stat().st_size > max_bytes:
                        continue
                    results = await self._search_in_file(filepath, regex, context_lines, results, max_results)
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break
        return json.dumps({"pattern": pattern, "matches": results})

    async def _search_in_file(self, filepath: Path, regex: re.Pattern, context_lines: int,
                                results: list, max_results: int) -> list:
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            return results

        for i, line in enumerate(lines, 1):
            if regex.search(line):
                try:
                    rel = filepath.relative_to(self.working_dir)
                except ValueError:
                    rel = filepath
                entry = {
                    "path": str(rel),
                    "line": i,
                    "text": line.strip(),
                }
                if context_lines > 0:
                    start_ctx = max(0, i - 1 - context_lines)
                    end_ctx = min(len(lines), i + context_lines)
                    entry["context"] = "".join(
                        f"{j}:{lines[j - 1]}" for j in range(start_ctx + 1, end_ctx + 1)
                    )
                results.append(entry)
                if len(results) >= max_results:
                    break
        return results
