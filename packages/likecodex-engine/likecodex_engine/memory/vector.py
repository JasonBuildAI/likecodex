"""Vector memory for project context and user preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class VectorMemory:
    """Semantic memory with optional chromadb backend."""

    def __init__(self, path: str | Path = ".likecodex/memory.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._collection = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.path.parent / "chroma"))
            self._collection = client.get_or_create_collection("likecodex_memory")
        except Exception:
            self._collection = None

    def add(self, text: str, metadata: dict[str, Any] | None = None, memory_type: str = "user") -> None:
        meta = {"type": memory_type, **(metadata or {})}
        entry = {"text": text, "metadata": meta}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        if self._collection is not None:
            doc_id = str(abs(hash(text + str(metadata))))
            self._collection.upsert(ids=[doc_id], documents=[text], metadatas=[meta])

    def search(self, query: str, top_k: int = 5, memory_type: str | None = None) -> list[dict[str, Any]]:
        results = self._search_impl(query, top_k)
        if memory_type:
            results = [r for r in results if r.get("metadata", {}).get("type") == memory_type]
        return results[:top_k]

    def list_by_type(self, memory_type: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        items: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("metadata", {}).get("type") == memory_type:
                    items.append(entry)
        return items[:limit]

    def _search_impl(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if self._collection is not None:
            try:
                result = self._collection.query(query_texts=[query], n_results=top_k)
                docs = result.get("documents", [[]])[0]
                metas = result.get("metadatas", [[]])[0]
                return [
                    {"text": doc, "metadata": meta or {}, "score": 1.0} for doc, meta in zip(docs, metas, strict=False)
                ]
            except Exception:
                pass
        return self._search_jsonl(query, top_k)

    def _search_jsonl(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        results = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                score = self._simple_score(query, entry.get("text", ""))
                results.append({**entry, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def _simple_score(query: str, text: str) -> float:
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        if not query_words:
            return 0.0
        intersection = query_words & text_words
        return len(intersection) / len(query_words)
