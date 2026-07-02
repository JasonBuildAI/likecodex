"""Code search tools: grep and simple symbol search.

Phase 7.3: Call Graph Visualization (Tool Layer)
- Future: expose a codegraph_viz() tool that returns a JSON edge list
  for frontend D3 force-directed graph or vis.js network rendering.
- Integrate with codegraph_callers() and codegraph_symbols() to
  build interactive call graphs.
"""

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
            "description": "Search for a pattern across files using grep with enhanced options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex or literal pattern to search"},
                    "glob": {"type": "string", "description": "File glob to limit search, e.g. '*.py'"},
                    "max_results": {"type": "integer", "default": 20},
                    "case_insensitive": {"type": "boolean", "default": False, "description": "Case insensitive search"},
                    "context_lines": {"type": "integer", "default": 0, "description": "Number of context lines to show before and after each match"},
                    "multiline": {"type": "boolean", "default": False, "description": "Enable multiline regex matching (. matches newline)"},
                },
                "required": ["pattern"],
            },
        }


    async def grep_files(self, pattern: str, glob: str | None = None, max_results: int = 20,
                          case_insensitive: bool = False, context_lines: int = 0,
                          multiline: bool = False) -> str:
        try:
            file_glob = glob or "**/*"
            if "*" in file_glob and "**" not in file_glob:
                file_glob = f"**/{file_glob}"
            files = list(self.working_dir.glob(file_glob))
            results = []
            flags = re.IGNORECASE if case_insensitive else 0
            if multiline:
                flags |= re.DOTALL
            regex = re.compile(pattern, flags)
            for file_path in files:
                if not file_path.is_file() or self._should_skip(file_path):
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                lines = text.splitlines()
                if multiline:
                    for match in regex.finditer(text):
                        start_pos = match.start()
                        line_no = text[:start_pos].count("\n") + 1
                        matched_text = match.group()[:200]
                        results.append(
                            {
                                "file": str(file_path.relative_to(self.working_dir)),
                                "line": line_no,
                                "content": matched_text,
                            }
                        )
                        if len(results) >= max_results:
                            break
                else:
                    for i, line in enumerate(lines, start=1):
                        if regex.search(line):
                            entry = {
                                "file": str(file_path.relative_to(self.working_dir)),
                                "line": i,
                                "content": line.strip(),
                            }
                            if context_lines > 0:
                                start_ctx = max(0, i - 1 - context_lines)
                                end_ctx = min(len(lines), i + context_lines)
                                entry["context"] = "\n".join(
                                    f"{j + 1}:{lines[j]}" for j in range(start_ctx, end_ctx)
                                )
                            results.append(entry)
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
        gi = self.working_dir / ".gitignore"
        if not gi.exists():
            return set()
        result = set()
        for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip().rstrip("/")
            if stripped and not stripped.startswith("#"):
                result.add(stripped)
        return result

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
        callers = [
            {"path": site.rpartition(":")[0], "line": int(site.rpartition(":")[2]) if site.rpartition(":")[2].isdigit() else 0}
            for site in graph.references.get(name, [])[:max_results]
        ]
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

    # ── Semantic search: search code by natural language intent ────────

    def semantic_search_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Search code by meaning/intent using embedding + symbol-based matching. "
                "Example queries: 'find the payment validation logic', "
                "'where is the user authentication handler', 'database connection setup'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of what to find",
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Optional file type filter, e.g. 'py', 'ts', 'rs'",
                    },
                },
                "required": ["query"],
            },
        }

    async def semantic_search(self, query: str, max_results: int = 10, file_type: str | None = None) -> str:
        """Search code by semantic intent — tries VectorMemory first, falls back to keyword+CodeGraph."""
        # Try embedding-based search first
        try:
            from likecodex_engine.memory.vector import VectorMemory
            memory = VectorMemory()
            vec_results = memory.search(query, top_k=max_results * 2)
        except Exception:
            vec_results = None

        if vec_results:
            clean = []
            for r in vec_results:
                text = r.get("text", "")[:500]
                if file_type and not text.lower().endswith(f".{file_type}"):
                    continue
                clean.append({"text": text, "score": r.get("score", 0.0)})
            if clean:
                return json.dumps({
                    "method": "embedding",
                    "query": query,
                    "results": clean[:max_results],
                    "total": len(clean),
                })

        # Fallback: keyword extraction + CodeGraph
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "find", "search", "show", "get", "where", "how", "what",
            "which", "this", "that", "these", "those", "i", "you", "we",
            "they", "he", "she", "it", "my", "your", "our", "their",
            "its", "to", "for", "of", "in", "on", "at", "by", "with",
            "from", "as", "into", "through", "during", "before", "after",
            "above", "below", "between", "out", "off", "over", "under",
            "again", "further", "then", "once", "here", "there", "all",
            "each", "every", "both", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "because", "but", "and", "or",
            "if", "while", "about", "up", "down", "also", "like",
            "handle", "handler", "implementation", "logic", "function",
            "method", "class", "component", "module", "file", "code",
            "setup", "config", "configuration", "connection", "service",
        }
        words = query.lower().split()
        keywords = [w.strip(".,;:!?\"'()[]{}") for w in words
                     if w.strip(".,;:!?\"'()[]{}") not in stop_words
                     and len(w.strip(".,;:!?\"'()[]{}")) > 2]

        if not keywords:
            keywords = [w for w in words if len(w) > 2][:3]

        try:
            graph = load_or_build(str(self.working_dir))
        except Exception as exc:
            return json.dumps({"error": f"Failed to load codegraph: {exc}", "results": []})

        scored: list[dict[str, Any]] = []
        for sym in graph.symbols:
            if file_type and not sym.path.endswith(f".{file_type}"):
                continue
            score = 0
            sym_lower = sym.name.lower()
            for kw in keywords:
                if kw in sym_lower:
                    score += 2
                if kw in sym.path.lower():
                    score += 1
            if score > 0:
                scored.append({
                    "name": sym.name,
                    "kind": sym.kind,
                    "path": sym.path,
                    "line": sym.line,
                    "relevance_score": score,
                })

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = scored[:max_results]

        return json.dumps({
            "query": query,
            "keywords": keywords,
            "results": results,
            "total_symbols": len(graph.symbols),
            "files": graph.file_count,
        })
