"""@ Mention search service — searches files, symbols, and special context for @ references."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# Static mention items reused across searches.
_STATIC_MENTIONS: list[dict[str, Any]] = [
    {
        "keywords": ["git", "diff", "change"],
        "item": {
            "id": "context:git-diff",
            "type": "git-diff",
            "label": "Git Changes",
            "description": "Unstaged and uncommitted changes",
            "icon": "git",
            "content": "[git diff]",
            "token_estimate": 2000,
            "relevance_score": 0.9,
        },
    },
    {
        "keywords": ["problem", "error", "diagnostic"],
        "item": {
            "id": "context:problems",
            "type": "problems",
            "label": "Problems",
            "description": "All errors and warnings in the project",
            "icon": "warning",
            "content": "[problems]",
            "token_estimate": 1500,
            "relevance_score": 0.7,
        },
    },
    {
        "keywords": ["tab", "open", "editor"],
        "item": {
            "id": "context:open-tabs",
            "type": "editor-tabs",
            "label": "Open Tabs",
            "description": "All files currently open in the editor",
            "icon": "tabs",
            "content": "[open tabs]",
            "token_estimate": 3000,
            "relevance_score": 0.8,
        },
    },
    {
        "keywords": ["web", "net", "search"],
        "item": {
            "id": "context:web",
            "type": "web",
            "label": "Web Search",
            "description": "Search the internet for latest information",
            "icon": "web",
            "content": "[web search]",
            "token_estimate": 100,
            "relevance_score": 0.5,
        },
    },
]


class MentionSearchService:
    """Search for files, symbols, and special context items for @ mentions."""

    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root

    async def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search all types of mentions."""
        results: list[dict[str, Any]] = []

        query_lower = query.lower().strip()

        # 1. Search files (fuzzy match on name and path)
        if query_lower:
            file_results = self._search_files(query_lower, limit // 2)
            results.extend(file_results)

        # 2. Special keywords (always show when no query or matching keywords)
        for entry in _STATIC_MENTIONS:
            if not query_lower or self._matches(query_lower, entry["keywords"]):
                results.append(entry["item"])

        # 3. Sort by relevance
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        return results[:limit]

    def _search_files(self, query_lower: str, limit: int) -> list[dict[str, Any]]:
        """Search files by name and path."""
        results: list[dict[str, Any]] = []
        skip_dirs = {
            "node_modules", "target", "__pycache__", ".git", ".next",
            "out", "dist", ".venv", ".pytest_cache", ".ruff_cache",
            "egg-info", ".likecodex",
        }

        for root, dirs, files in os.walk(self.root):
            # Filter out skip directories
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

            for file in files:
                if len(results) >= limit:
                    return results

                if query_lower in file.lower():
                    full_path = Path(root) / file
                    try:
                        rel_path = full_path.relative_to(self.root)
                        size = full_path.stat().st_size if full_path.exists() else 0
                        # Score: exact match > starts with > contains
                        name_lower = file.lower()
                        if name_lower == query_lower:
                            score = 1.0
                        elif name_lower.startswith(query_lower):
                            score = 0.8
                        else:
                            score = 0.5

                        results.append({
                            "id": f"file:{rel_path}",
                            "type": "file",
                            "label": file,
                            "description": str(rel_path).replace("\\", "/"),
                            "icon": "file",
                            "content": f"[file: {rel_path}]",
                            "token_estimate": min(size // 4, 2000),
                            "relevance_score": score,
                        })
                    except (ValueError, OSError):
                        continue

        return results

    def _matches(self, query_lower: str, keywords: list[str]) -> bool:
        return any(kw in query_lower or query_lower in kw for kw in keywords)
