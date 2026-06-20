"""Code search tools: grep and simple symbol search."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import aiohttp

from likecodex_engine.tools.codegraph import build_codegraph, load_or_build, save_codegraph


class CodeSearchTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()
        self.indexer_url = os.environ.get("LIKECODEX_INDEXER_URL", "http://127.0.0.1:8080/index/search")
        self._gitignore_patterns: set[str] | None = None

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

    def _load_gitignore(self) -> set[str]:
        patterns: set[str] = set()
        gi = self.working_dir / ".gitignore"
        if gi.exists():
            for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.add(line.rstrip("/"))
        return patterns

    def _gitignore_skip(self, path: Path) -> bool:
        rel = path.relative_to(self.working_dir)
        parts = rel.parts
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "target"}
        if any(part in skip_dirs for part in parts):
            return True
        patterns = getattr(self, "_gitignore_patterns", None)
        if patterns is None:
            self._gitignore_patterns = self._load_gitignore()
            patterns = self._gitignore_patterns
        rel_str = str(rel).replace("\\", "/")
        for pat in patterns:
            if pat.endswith("/"):
                if rel_str.startswith(pat) or f"/{pat}" in f"/{rel_str}/":
                    return True
            elif pat in rel_str or rel_str == pat:
                return True
        return False

    def _should_skip(self, path: Path) -> bool:
        return self._gitignore_skip(path)

    def codegraph_search_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Search the code graph for symbol definitions (functions, classes, structs, "
                "interfaces, types) by exact or substring name. Faster and more precise than grep."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Symbol name or substring"},
                    "kind": {"type": "string", "description": "Optional kind filter (function/class/...)"},
                    "max_results": {"type": "integer", "default": 30},
                },
                "required": ["name"],
            },
        }

    async def codegraph_search(self, name: str, kind: str | None = None, max_results: int = 30) -> str:
        graph = load_or_build(self.working_dir)
        lowered = name.lower()
        results = []
        for sym in graph.symbols:
            if lowered not in sym.name.lower():
                continue
            if kind and sym.kind != kind:
                continue
            results.append({"name": sym.name, "kind": sym.kind, "path": sym.path, "line": sym.line})
            if len(results) >= max_results:
                break
        results.sort(key=lambda r: (r["name"] != name, r["path"], r["line"]))
        return json.dumps({"query": name, "results": results, "count": len(results)})

    def codegraph_symbols_schema(self) -> dict[str, Any]:
        return {
            "description": "List all symbol definitions in a given file from the code graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                },
                "required": ["path"],
            },
        }

    async def codegraph_symbols(self, path: str) -> str:
        graph = load_or_build(self.working_dir)
        norm = path.replace("\\", "/")
        symbols = [
            {"name": s.name, "kind": s.kind, "line": s.line} for s in graph.symbols if s.path.replace("\\", "/") == norm
        ]
        symbols.sort(key=lambda s: s["line"])
        return json.dumps({"path": path, "symbols": symbols, "count": len(symbols)})

    def codegraph_callers_schema(self) -> dict[str, Any]:
        return {
            "description": "Find call/reference sites of a known symbol across the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact symbol name"},
                    "max_results": {"type": "integer", "default": 50},
                },
                "required": ["name"],
            },
        }

    async def codegraph_callers(self, name: str, max_results: int = 50) -> str:
        graph = load_or_build(self.working_dir)
        sites = graph.references.get(name, [])[:max_results]
        callers = []
        for site in sites:
            file_part, _, line_part = site.rpartition(":")
            callers.append({"path": file_part, "line": int(line_part) if line_part.isdigit() else 0})
        return json.dumps({"symbol": name, "callers": callers, "count": len(callers)})

    def codegraph_reindex_schema(self) -> dict[str, Any]:
        return {
            "description": "Rebuild the code graph index for the workspace (use after large refactors).",
            "parameters": {"type": "object", "properties": {}},
        }

    async def codegraph_reindex(self) -> str:
        graph = build_codegraph(self.working_dir)
        save_codegraph(graph)
        return json.dumps(
            {
                "reindexed": True,
                "symbols": len(graph.symbols),
                "files": graph.file_count,
            }
        )
