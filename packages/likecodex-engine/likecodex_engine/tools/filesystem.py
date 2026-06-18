"""Filesystem tools for the agent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import aiofiles

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

    def read_file_schema(self) -> dict[str, Any]:
        return {
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path within the workspace"},
                },
                "required": ["path"],
            },
        }

    async def read_file(self, path: str) -> str:
        try:
            target = self._resolve(path)
        except PermissionError as e:
            return json.dumps({"error": str(e)})
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if not target.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        size = target.stat().st_size
        if size > MAX_READ_BYTES:
            return json.dumps({"error": f"File too large ({size} bytes, max {MAX_READ_BYTES})"})
        async with aiofiles.open(target, encoding="utf-8") as f:
            content = await f.read()
        return json.dumps({"path": str(target.relative_to(self.working_dir)), "content": content})

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
        try:
            target = self._resolve(path)
        except PermissionError as e:
            return json.dumps({"error": str(e)})
        target.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target, "w", encoding="utf-8") as f:
            await f.write(content)
        return json.dumps(
            {
                "path": str(target.relative_to(self.working_dir)),
                "written": True,
                "bytes": len(content),
            }
        )

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
        try:
            target = self._resolve(path)
        except PermissionError as e:
            return json.dumps({"error": str(e)})
        if not target.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        if not target.is_dir():
            return json.dumps({"error": f"Not a directory: {path}"})
        entries = []
        for entry in target.iterdir():
            entries.append(
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else None,
                }
            )
        return json.dumps({"path": str(target.relative_to(self.working_dir)), "entries": entries})

    def search_files_schema(self) -> dict[str, Any]:
        return {
            "description": "Search file contents for a regex pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["pattern"],
            },
        }

    async def search_files(self, pattern: str, path: str = ".") -> str:
        import re

        try:
            target = self._resolve(path)
        except PermissionError as e:
            return json.dumps({"error": str(e)})
        results = []
        regex = re.compile(pattern)
        for root, dirs, files in os.walk(target):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if should_skip_path(self.working_dir, root_path):
                continue
            for name in files:
                filepath = root_path / name
                if should_skip_path(self.working_dir, filepath):
                    continue
                try:
                    with open(filepath, encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                rel = filepath.relative_to(self.working_dir)
                                results.append({"path": str(rel), "line": i, "text": line.strip()})
                                if len(results) >= 50:
                                    break
                        if len(results) >= 50:
                            break
                except OSError:
                    continue
            if len(results) >= 50:
                break
        return json.dumps({"pattern": pattern, "matches": results})
