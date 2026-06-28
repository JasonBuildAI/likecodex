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


def _read_jsonl_messages(path: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if not path.exists():
        return messages
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


class HistoryTools:
    def __init__(self, working_dir: str, session_db_path: str = ".likecodex/sessions.db") -> None:
        self.working_dir = Path(working_dir).resolve()
        self.session_db_path = session_db_path
        self.global_dir = Path.home() / ".likecodex" / "sessions"

    @staticmethod
    def _glob_jsonl_texts(directory: Path, *, recursive: bool = False) -> list[tuple[str, str]]:
        """Read all .jsonl files in a directory, returning [(path, text), ...]."""
        if not directory.exists():
            return []
        glob_fn = directory.rglob if recursive else directory.glob
        return [
            (str(p), p.read_text(encoding="utf-8", errors="replace"))
            for p in sorted(glob_fn("*.jsonl"))
        ]

    def _collect_docs(self, scope: str) -> list[tuple[str, str, str]]:
        docs: list[tuple[str, str, str]] = []
        archive_dir = self.working_dir / ".likecodex" / "archive"
        for path, text in self._glob_jsonl_texts(archive_dir):
            docs.append((path, "archive", text))
        sessions_dir = self.working_dir / ".likecodex" / "sessions"
        for path, text in self._glob_jsonl_texts(sessions_dir):
            docs.append((path, "session", text))
        if scope == "global":
            for path, text in self._glob_jsonl_texts(self.global_dir, recursive=True):
                docs.append((path, "global", text))
        return docs

    def _around_slice(
        self,
        path: Path,
        message_index: int,
        before: int,
        after: int,
    ) -> dict[str, Any]:
        messages = _read_jsonl_messages(path)
        if not messages:
            return {"path": str(path), "messages": [], "hint": "No messages in file"}
        idx = max(0, min(message_index, len(messages) - 1))
        start = max(0, idx - before)
        end = min(len(messages), idx + after + 1)
        return {
            "path": str(path),
            "message_index": idx,
            "before": before,
            "after": after,
            "messages": messages[start:end],
        }

    def history_schema(self) -> dict[str, Any]:
        return {
            "description": "Search compacted conversation archives (BM25) or fetch context around a message index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "scope": {"type": "string", "enum": ["project", "global"], "default": "project"},
                    "operation": {"type": "string", "enum": ["search", "around"], "default": "search"},
                    "message_index": {"type": "integer", "description": "Target message index for around"},
                    "before": {"type": "integer", "default": 3},
                    "after": {"type": "integer", "default": 3},
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
        message_index: int | None = None,
        before: int = 3,
        after: int = 3,
    ) -> str:
        docs = self._collect_docs(scope)
        if operation == "around" and message_index is not None:
            sessions_dir = self.working_dir / ".likecodex" / "sessions"
            live = sorted(sessions_dir.glob("*.jsonl")) if sessions_dir.exists() else []
            target = live[-1] if live else None
            if target is None and docs:
                target = Path(docs[0][0])
            if target is None:
                return json.dumps({"messages": [], "hint": "No session JSONL found for around"})
            return json.dumps(self._around_slice(target, message_index, before, after))

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
            path = Path(hits[0]["path"])
            idx = message_index if message_index is not None else 0
            return json.dumps(self._around_slice(path, idx, before, after))
        return json.dumps({"hits": hits, "query": query})
