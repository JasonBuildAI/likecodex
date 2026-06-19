"""Lightweight code symbol index (offline fallback)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from likecodex_engine.tools.codegraph import load_or_build

SYMBOL_RE = {
    "python": re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", re.MULTILINE),
    "javascript": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+(\w+)", re.MULTILINE),
    "go": re.compile(r"^\s*func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", re.MULTILINE),
}


class CodeIndexTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    def code_index_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Offline symbol index fallback. Prefer lsp_* tools for semantics; "
                "use code_index for quick outlines when LSP is unavailable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["outline", "search"]},
                    "path": {"type": "string", "default": "."},
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["action"],
            },
        }

    async def code_index(
        self,
        action: str,
        path: str = ".",
        query: str = "",
        limit: int = 50,
    ) -> str:
        graph = load_or_build(str(self.working_dir))
        symbols = [{"name": s.name, "kind": s.kind, "file": s.path, "line": s.line} for s in graph.symbols]
        if action == "search":
            q = query.lower()
            hits = [s for s in symbols if q in s.get("name", "").lower()][:limit]
            return json.dumps({"symbols": hits})
        prefix = str((self.working_dir / path).resolve().relative_to(self.working_dir)) if path != "." else "."
        if prefix == ".":
            hits = symbols[:limit]
        else:
            hits = [s for s in symbols if s.get("file", "").startswith(prefix.replace("\\", "/"))][:limit]
        return json.dumps({"symbols": hits, "path": path})
