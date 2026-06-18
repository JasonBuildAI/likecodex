"""Code search tools: grep and simple symbol search."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import aiohttp


class CodeSearchTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()
        self.indexer_url = os.environ.get("LIKECODEX_INDEXER_URL", "http://127.0.0.1:8080/index/search")

    def index_search_schema(self) -> dict[str, Any]:
        return {
            "description": "Search indexed files by filename pattern via the Rust indexer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Filename substring to match"},
                },
                "required": ["pattern"],
            },
        }

    async def index_search(self, pattern: str) -> str:
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(self.indexer_url, params={"pattern": pattern}) as resp,
            ):
                body = await resp.json()
                return json.dumps(body)
        except Exception as exc:
            return json.dumps({"error": str(exc), "results": []})

    def grep_schema(self) -> dict[str, Any]:
        return {
            "description": "Search for a pattern across files using grep.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex or literal pattern to search"},
                    "glob": {"type": "string", "description": "File glob to limit search, e.g. '*.py'"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["pattern"],
            },
        }

    async def grep_files(self, pattern: str, glob: str | None = None, max_results: int = 20) -> str:
        try:
            file_glob = glob or "**/*"
            if "*" in file_glob and "**" not in file_glob:
                file_glob = f"**/{file_glob}"
            files = list(self.working_dir.glob(file_glob))
            results = []
            regex = re.compile(pattern)
            for file_path in files:
                if not file_path.is_file() or self._should_skip(file_path):
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        results.append(
                            {
                                "file": str(file_path.relative_to(self.working_dir)),
                                "line": i,
                                "content": line.strip(),
                            }
                        )
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
            return json.dumps({"pattern": pattern, "glob": file_glob, "results": results, "count": len(results)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def find_symbol_schema(self) -> dict[str, Any]:
        return {
            "description": "Find definitions of a symbol (function/class/variable) by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Symbol name to find"},
                    "max_results": {"type": "integer", "default": 20},
                },
                "required": ["name"],
            },
        }

    async def find_symbol(self, name: str, max_results: int = 20) -> str:
        try:
            patterns = [
                rf"^\s*(?:def|class)\s+{re.escape(name)}\b",
                rf"\b{name}\s*[:=]",
            ]
            results = []
            for file_path in self.working_dir.rglob("*"):
                if not file_path.is_file() or self._should_skip(file_path):
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if any(re.search(p, line) for p in patterns):
                        results.append(
                            {
                                "file": str(file_path.relative_to(self.working_dir)),
                                "line": i,
                                "content": line.strip(),
                            }
                        )
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
            return json.dumps({"symbol": name, "results": results, "count": len(results)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _should_skip(self, path: Path) -> bool:
        parts = path.relative_to(self.working_dir).parts
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "target"}
        return any(part in skip_dirs for part in parts)
