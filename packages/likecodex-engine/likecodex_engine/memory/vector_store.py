"""Vector store with automatic backend detection and graceful degradation.

Backend priority:
1. ChromaDB (persistent, feature-rich, preferred)
2. NumPy + JSONL (zero extra dependencies, always available)

All backends expose the same ``VectorStore`` interface.
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NumPy / JSONL fallback store
# ---------------------------------------------------------------------------

class _NumpyJsonlStore:
    """Lightweight vector store using NumPy (for search) + JSONL (for persistence).

    Used when ChromaDB is not available.
    """

    def __init__(self, path: str | Path = ".likecodex/vector_store") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._jsonl_path = self._path / "vectors.jsonl"
        self._entries: dict[str, dict[str, Any]] = {}  # id -> entry
        self._embeddings: dict[str, list[float]] = {}  # id -> vector
        self._dirty = False
        self._np = None  # lazy import
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._jsonl_path.exists():
            return
        with self._jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry_id = data.get("id", str(uuid.uuid4().hex))
                self._entries[entry_id] = {
                    "id": entry_id,
                    "text": data.get("text", ""),
                    "metadata": data.get("metadata", {}),
                    "embedding": None,  # loaded separately
                }
                emb = data.get("embedding")
                if emb is not None:
                    self._embeddings[entry_id] = emb
        logger.debug("Loaded %d entries from %s", len(self._entries), self._jsonl_path)

    def _save(self) -> None:
        with self._jsonl_path.open("w", encoding="utf-8") as f:
            for entry_id, entry in self._entries.items():
                row = {
                    "id": entry_id,
                    "text": entry["text"],
                    "metadata": entry["metadata"],
                    "embedding": self._embeddings.get(entry_id),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._dirty = False
        logger.debug("Saved %d entries to %s", len(self._entries), self._jsonl_path)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, entry_id: str | None, text: str, embedding: list[float], metadata: dict[str, Any]) -> str:
        entry_id = entry_id or uuid.uuid4().hex
        self._entries[entry_id] = {
            "id": entry_id,
            "text": text,
            "metadata": {**metadata, "stored_at": time.time()},
            "embedding": embedding,
        }
        self._embeddings[entry_id] = embedding
        self._dirty = True
        if len(self._entries) % 10 == 0:
            self._save()
        return entry_id

    def add_batch(
        self,
        ids: list[str | None],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> list[str]:
        result_ids: list[str] = []
        for i, text in enumerate(texts):
            eid = ids[i] if i < len(ids) else None
            meta = metadatas[i] if i < len(metadatas) else {}
            result_ids.append(self.add(eid, text, embeddings[i], meta))
        return result_ids

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if not self._entries:
            return []

        scored: list[tuple[float, str]] = []
        for entry_id, emb in self._embeddings.items():
            sim = self._cosine_sim(query_embedding, emb)
            scored.append((sim, entry_id))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[dict[str, Any]] = []
        for sim, eid in scored[:top_k]:
            entry = self._entries[eid]
            results.append({
                "id": eid,
                "text": entry["text"],
                "metadata": dict(entry["metadata"]),
                "score": sim,
                "embedding": self._embeddings.get(eid),
            })
        return results

    def delete(self, ids: list[str]) -> None:
        for eid in ids:
            self._entries.pop(eid, None)
            self._embeddings.pop(eid, None)
        self._dirty = True

    def get(self, entry_id: str) -> dict[str, Any] | None:
        entry = self._entries.get(entry_id)
        if entry is None:
            return None
        return {
            "id": entry_id,
            "text": entry["text"],
            "metadata": dict(entry["metadata"]),
            "embedding": self._embeddings.get(entry_id),
        }

    def count(self) -> int:
        return len(self._entries)

    def close(self) -> None:
        if self._dirty:
            self._save()

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# ChromaDB store
# ---------------------------------------------------------------------------

class _ChromaStore:
    """Persistent vector store backed by ChromaDB."""

    def __init__(
        self,
        path: str | Path = ".likecodex/vector_store",
        collection_name: str = "likecodex_memory",
    ) -> None:
        import chromadb

        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._path / "chroma"))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, entry_id: str | None, text: str, embedding: list[float], metadata: dict[str, Any]) -> str:
        eid = entry_id or uuid.uuid4().hex
        meta = {**metadata, "stored_at": time.time()}
        # ChromaDB expects metadata values to be str/int/float/bool
        meta = _sanitize_metadata(meta)
        self._collection.add(
            ids=[eid],
            embeddings=[embedding],
            documents=[text],
            metadatas=[meta],
        )
        return eid

    def add_batch(
        self,
        ids: list[str | None],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> list[str]:
        resolved_ids: list[str] = []
        resolved_texts: list[str] = []
        resolved_embs: list[list[float]] = []
        resolved_metas: list[dict[str, Any]] = []

        for i, text in enumerate(texts):
            eid = ids[i] if i < len(ids) and ids[i] is not None else uuid.uuid4().hex
            meta = metadatas[i] if i < len(metadatas) else {}
            meta["stored_at"] = time.time()
            resolved_ids.append(eid)
            resolved_texts.append(text)
            resolved_embs.append(embeddings[i])
            resolved_metas.append(_sanitize_metadata(meta))

        self._collection.add(
            ids=resolved_ids,
            embeddings=resolved_embs,
            documents=resolved_texts,
            metadatas=resolved_metas,
        )
        return resolved_ids

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances", "embeddings"],
        )
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]
        embs = result.get("embeddings", [[]])[0]

        entries: list[dict[str, Any]] = []
        for doc, meta, dist, emb in zip(docs, metas, dists, embs, strict=False):
            # Convert distance to similarity score (cosine distance → cosine similarity)
            score = 1.0 - dist if dist is not None else 0.0
            entries.append({
                "text": doc or "",
                "metadata": meta or {},
                "score": max(0.0, min(1.0, score)),
                "embedding": emb,
            })
        return entries

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)

    def count(self) -> int:
        return self._collection.count()

    def close(self) -> None:
        pass  # ChromaDB handles persistence itself


# ---------------------------------------------------------------------------
# Metadata sanitisation
# ---------------------------------------------------------------------------

def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Ensure all metadata values are ChromaDB-compatible types."""
    sanitized: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)):
            sanitized[k] = v
        elif isinstance(v, (list, dict)) and len(json.dumps(v)) < 500:
            sanitized[k] = json.dumps(v, ensure_ascii=False)
        elif v is None:
            sanitized[k] = ""
        else:
            sanitized[k] = str(v)
    return sanitized


# ---------------------------------------------------------------------------
# Unified VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """Unified vector store with automatic backend detection.

    Prefers ChromaDB (persistent, fast ANN search) and falls back to a
    pure-Python NumPy + JSONL store when ChromaDB is unavailable.

    Usage::

        store = VectorStore(".likecodex/vector_store")
        vid = store.add(None, "some text", embedding_vector, {"source": "user"})
        results = store.search(query_embedding, top_k=5)
        store.delete([vid])
    """

    def __init__(
        self,
        path: str | Path = ".likecodex/vector_store",
        collection_name: str = "likecodex_memory",
    ) -> None:
        self._path = Path(path)
        self._store: _ChromaStore | _NumpyJsonlStore = self._init_store(collection_name)

    def _init_store(self, collection_name: str) -> _ChromaStore | _NumpyJsonlStore:
        try:
            import chromadb  # noqa: F401

            store = _ChromaStore(self._path, collection_name)
            logger.info("VectorStore backend: ChromaDB")
            return store
        except ImportError:
            logger.info("VectorStore backend: NumPy + JSONL (ChromaDB not available)")
            return _NumpyJsonlStore(self._path)

    @property
    def backend(self) -> str:
        return "chromadb" if isinstance(self._store, _ChromaStore) else "numpy+jsonl"

    def add(
        self,
        entry_id: str | None,
        text: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        return self._store.add(entry_id, text, embedding, metadata or {})

    def add_batch(
        self,
        ids: list[str | None],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        metadatas = metadatas or [{}] * len(texts)
        return self._store.add_batch(ids, texts, embeddings, metadatas)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        return self._store.search(query_embedding, top_k)

    def delete(self, ids: list[str]) -> None:
        self._store.delete(ids)

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """Retrieve a single entry by ID (only works for NumPy+JSONL backend)."""
        if isinstance(self._store, _NumpyJsonlStore):
            return self._store.get(entry_id)
        return None

    def count(self) -> int:
        return self._store.count()

    def close(self) -> None:
        self._store.close()
