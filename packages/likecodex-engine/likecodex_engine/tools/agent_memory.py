"""Agent-initiated persistent memory (remember/forget/search)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s[:60] or "fact"


class AgentMemoryTools:
    def __init__(self, working_dir: str) -> None:
        self.memory_dir = Path(working_dir).resolve() / ".likecodex" / "agent_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.memory_dir / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def remember_schema(self) -> dict[str, Any]:
        return {
            "description": "Save a durable fact to agent memory. Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short identifier for the fact"},
                    "content": {"type": "string", "description": "The fact to remember"},
                },
                "required": ["key", "content"],
            },
        }

    def forget_schema(self) -> dict[str, Any]:
        return {
            "description": "Archive a memory fact. Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        }

    def memory_search_schema(self) -> dict[str, Any]:
        return {
            "description": "Search saved agent memory facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        }

    def _path_for(self, key: str) -> Path:
        return self.memory_dir / f"{_slug(key)}.md"

    async def remember(self, key: str, content: str) -> str:
        path = self._path_for(key)
        path.write_text(content.strip() + "\n", encoding="utf-8")
        return json.dumps({"saved": True, "key": key, "path": str(path.relative_to(self.memory_dir.parent.parent))})

    async def forget(self, key: str) -> str:
        path = self._path_for(key)
        if not path.exists():
            return json.dumps({"error": f"No memory for key {key!r}"})
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archived = self.archive_dir / f"{_slug(key)}-{ts}.md"
        archived.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.unlink()
        return json.dumps({"forgotten": True, "key": key, "archived": str(archived.name)})

    async def memory_search(self, query: str, limit: int = 10) -> str:
        q = query.lower()
        hits = [
            {"key": p.stem, "content": text[:500]}
            for p in sorted(self.memory_dir.glob("*.md"))
            if q in (text := p.read_text(encoding="utf-8", errors="replace")).lower() or q in p.stem.lower()
        ]
        return json.dumps({"hits": hits[:limit]})
