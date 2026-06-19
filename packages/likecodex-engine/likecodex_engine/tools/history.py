"""BM25 search over session archives and history."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_./-]+", text.lower())


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], avg_dl: float, df: Counter, n_docs: int) -> float:
    if not doc_tokens:
        return 0.0
    k1, b = 1.5, 0.75
    dl = len(doc_tokens)
    tf = Counter(doc_tokens)
    score = 0.0
    for term in query_tokens:
        if term not in tf:
            continue
        idf = math.log(1 + (n_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
        freq = tf[term]
        score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / avg_dl))
    return score


class HistoryTools:
    def __init__(self, working_dir: str, session_db_path: str = ".likecodex/sessions.db") -> None:
        self.working_dir = Path(working_dir).resolve()
        self.session_db_path = session_db_path
        self.global_dir = Path.home() / ".likecodex" / "sessions"

    def _collect_docs(self, scope: str) -> list[tuple[str, str, str]]:
        docs: list[tuple[str, str, str]] = []
        archive_dir = self.working_dir / ".likecodex" / "archive"
        if archive_dir.exists():
            for path in sorted(archive_dir.glob("*.jsonl")):
                text = path.read_text(encoding="utf-8", errors="replace")
                docs.append((str(path), "archive", text))
        if scope == "global" and self.global_dir.exists():
            for path in self.global_dir.rglob("*.jsonl"):
                text = path.read_text(encoding="utf-8", errors="replace")
                docs.append((str(path), "global", text))
        return docs

    def history_schema(self) -> dict[str, Any]:
        return {
            "description": "Search compacted conversation archives (BM25). scope=project|global.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "scope": {"type": "string", "enum": ["project", "global"], "default": "project"},
                    "operation": {"type": "string", "enum": ["search", "around"], "default": "search"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        }

    async def history(
        self,
        query: str,
        scope: str = "project",
        operation: str = "search",
        limit: int = 5,
    ) -> str:
        docs = self._collect_docs(scope)
        if not docs:
            return json.dumps({"hits": [], "hint": "No archived history found. Compaction creates archives."})
        query_tokens = _tokenize(query)
        all_tokens = [_tokenize(text) for _, _, text in docs]
        avg_dl = sum(len(t) for t in all_tokens) / max(len(all_tokens), 1)
        df: Counter = Counter()
        for tokens in all_tokens:
            for term in set(tokens):
                df[term] += 1
        scored = []
        for (path, kind, text), tokens in zip(docs, all_tokens, strict=False):
            score = _bm25_score(query_tokens, tokens, avg_dl, df, len(docs))
            if score > 0:
                scored.append((score, path, kind, text))
        scored.sort(key=lambda x: -x[0])
        hits = []
        for score, path, kind, text in scored[:limit]:
            snippet = text[:500].replace("\n", " ")
            hits.append({"score": round(score, 3), "path": path, "kind": kind, "snippet": snippet})
        if operation == "around" and hits:
            path = hits[0]["path"]
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return json.dumps({"path": path, "content": content[:8000]})
        return json.dumps({"hits": hits, "query": query})
