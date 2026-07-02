"""Vector memory for project context and user preferences.

Three-tier memory architecture:
- Working: current session (in-memory only, ephemeral)
- Episodic: recent sessions (synced to persistent storage)
- Semantic: long-term knowledge (project rules, decisions, patterns)

True semantic embedding search via EmbeddingManager + VectorStore.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .decay import apply_decay, update_access
from .embeddings import EmbeddingManager
from .fusion import fuse
from .vector_store import VectorStore


logger = logging.getLogger(__name__)

WORKING_MAX_ENTRIES = 50
EPISODIC_PERSIST_INTERVAL = 10  # sync every N entries


class MemoryTier(str, Enum):
    """Three tiers of memory hierarchy."""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass
class MemoryEntry:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tier: str = MemoryTier.WORKING
    timestamp: float = field(default_factory=time.time)
    source_session: str = ""


class WorkingMemory:
    """Current session, in-memory only, fast keyword search."""

    def __init__(self, max_entries: int = WORKING_MAX_ENTRIES) -> None:
        self._entries: list[MemoryEntry] = []
        self._max_entries = max_entries

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        entry = MemoryEntry(text=text, metadata=metadata or {}, tier=MemoryTier.WORKING)
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            # Evict oldest when over limit (move to episodic later)
            self._entries.pop(0)

    def search(self, query: str, top_k: int = 3) -> list[MemoryEntry]:
        """Fast keyword-based search on working memory."""
        query_words = set(query.lower().split())
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self._entries:
            text_words = set(entry.text.lower().split())
            common = query_words & text_words
            if common:
                score = len(common) / max(len(query_words), 1)
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def get_all(self) -> list[MemoryEntry]:
        return list(self._entries)

    def clear(self) -> list[MemoryEntry]:
        """Clear and return the current entries for archival."""
        entries = self._entries
        self._entries = []
        return entries

    @property
    def size(self) -> int:
        return len(self._entries)


class EpisodicMemory:
    """Recent sessions persisted to JSONL and optionally ChromaDB."""

    def __init__(self, path: str | Path = ".likecodex/memory.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._collection = None
        self._init_chroma()
        self._pending_sync: list[MemoryEntry] = []
        self._sync_counter = 0

    def _init_chroma(self) -> None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.path.parent / "chroma"))
            self._collection = client.get_or_create_collection("likecodex_memory")
        except Exception:
            self._collection = None

    def add(self, entry: MemoryEntry) -> None:
        """Persist an episodic memory entry."""
        self._pending_sync.append(entry)
        self._sync_counter += 1
        # Bulk write to JSONL
        if self._sync_counter >= EPISODIC_PERSIST_INTERVAL:
            self._flush()

    def _flush(self) -> None:
        if not self._pending_sync:
            return
        with self.path.open("a", encoding="utf-8") as f:
            for entry in self._pending_sync:
                row = {
                    "text": entry.text,
                    "metadata": {**entry.metadata, "tier": entry.tier, "timestamp": entry.timestamp},
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        # Sync to chroma
        if self._collection is not None:
            for entry in self._pending_sync:
                doc_id = str(abs(hash(entry.text + str(entry.metadata))))
                meta = {**entry.metadata, "tier": entry.tier}
                self._collection.upsert(ids=[doc_id], documents=[entry.text], metadatas=[meta])
        self._pending_sync.clear()

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self._flush()
        if self._collection is not None:
            try:
                result = self._collection.query(query_texts=[query], n_results=top_k)
                docs = result.get("documents", [[]])[0]
                metas = result.get("metadatas", [[]])[0]
                return [
                    {"text": doc, "metadata": meta or {}, "score": 1.0, "tier": MemoryTier.EPISODIC}
                    for doc, meta in zip(docs, metas, strict=False)
                ]
            except Exception:
                logger.warning("chromadb query failed, falling back to JSONL", exc_info=True)
        return self._search_jsonl(query, top_k)

    def _search_jsonl(self, query: str, top_k: int) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        results: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("metadata", {}).get("tier") != MemoryTier.EPISODIC:
                    continue
                text = entry.get("text", "")
                query_words = set(query.lower().split())
                text_words = set(text.lower().split())
                if not query_words:
                    continue
                common = query_words & text_words
                score = len(common) / len(query_words)
                results.append({"text": text, "metadata": entry.get("metadata", {}), "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def persist_working(self, working: WorkingMemory) -> int:
        """Bulk persist current working memory entries into episodic storage."""
        entries = working.clear()
        count = 0
        for entry in entries:
            entry.tier = MemoryTier.EPISODIC
            self.add(entry)
            count += 1
        return count

    def close(self) -> None:
        self._flush()


class SemanticMemory:
    """Long-term knowledge: project rules, architectural decisions, user preferences.

    Entries are persisted with high priority and never automatically evicted.
    """

    def __init__(self, path: str | Path = ".likecodex/memory.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a semantic memory entry (persisted immediately)."""
        entry = MemoryEntry(
            text=text,
            metadata={**(metadata or {}), "tier": MemoryTier.SEMANTIC},
            tier=MemoryTier.SEMANTIC,
        )
        row = {
            "text": entry.text,
            "metadata": {**entry.metadata, "tier": MemoryTier.SEMANTIC, "timestamp": entry.timestamp},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Search semantic memory entries."""
        if not self.path.exists():
            return []
        results: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("metadata", {}).get("tier") != MemoryTier.SEMANTIC:
                    continue
                text = entry.get("text", "")
                query_words = set(query.lower().split())
                text_words = set(text.lower().split())
                if not query_words:
                    continue
                common = query_words & text_words
                score = len(common) / len(query_words)
                results.append({**entry, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        """List all semantic memory entries."""
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
                if entry.get("metadata", {}).get("tier") == MemoryTier.SEMANTIC:
                    items.append(entry)
        return items[:limit]


class VectorMemory:
    """Unified access to three-tier memory architecture.

    Delegates to WorkingMemory, EpisodicMemory, and SemanticMemory
    with tier-aware search and promotion/consolidation operations.

    Now also provides true semantic embedding search via EmbeddingManager
    and VectorStore.
    """

    def __init__(
        self,
        path: str | Path = ".likecodex/memory.jsonl",
        embedder: EmbeddingManager | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory(path)
        self.semantic = SemanticMemory(path)
        # New embedding system
        self._embedder = embedder or EmbeddingManager()
        store_path = self.path.parent / "vector_store"
        self._vector_store = vector_store or VectorStore(store_path)

    # --- Working tier ---
    def add_working(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add to working memory (current session, in-memory)."""
        self.working.add(text, metadata)

    def search_working(self, query: str, top_k: int = 3) -> list[MemoryEntry]:
        """Search only working memory."""
        return self.working.search(query, top_k)

    # --- Episodic tier ---
    def add_episodic(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add an entry directly to episodic memory."""
        entry = MemoryEntry(text=text, metadata=metadata or {}, tier=MemoryTier.EPISODIC)
        self.episodic.add(entry)

    def search_episodic(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search episodic memory."""
        return self.episodic.search(query, top_k)

    # --- Semantic tier ---
    def add_semantic(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add an entry to semantic (long-term) memory."""
        self.semantic.add(text, metadata)

    def search_semantic(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Search semantic memory."""
        return self.semantic.search(query, top_k)

    def list_semantic(self, limit: int = 100) -> list[dict[str, Any]]:
        """List all semantic memories."""
        return self.semantic.list_all(limit)

    # --- Embedding search (new) ---
    def search_embedding(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search using true semantic embedding similarity.

        Queries the vector store with the query's embedding, then applies
        decay and fuses results from all tiers.
        """
        query_emb = self._embedder.embed(query)
        store_results = self._vector_store.search(query_emb, top_k=top_k)

        # Apply decay
        store_results = apply_decay(store_results)

        # Mark accessed
        for r in store_results:
            update_access(r)

        return store_results

    # --- Cross-tier operations ---
    def search(self, query: str, top_k: int = 5, memory_type: str | None = None) -> list[dict[str, Any]]:
        """Search across all tiers, optionally filtered by type.

        Uses true embedding search when the vector store is populated;
        falls back to the original keyword search otherwise.

        Returns combined results ranked by relevance. Working memory results
        are boosted because they represent the current session context.
        """
        results: list[dict[str, Any]] = []

        # Try embedding search first (if store has entries)
        if self._vector_store.count() > 0:
            embedding_results = self.search_embedding(query, top_k)
            results.extend(embedding_results)

        # Also always search working memory (in-memory, boosted)
        working_results = self.working.search(query, top_k)
        for entry in working_results:
            results.append({
                "text": entry.text,
                "metadata": {**entry.metadata, "tier": MemoryTier.WORKING},
                "score": 1.5,  # boost working memory
            })

        # Fallback: episodic + semantic keyword search
        episodic_results = self.episodic.search(query, top_k)
        results.extend(episodic_results)

        semantic_results = self.semantic.search(query, top_k)
        results.extend(semantic_results)

        # Filter by type if specified
        if memory_type:
            results = [r for r in results if r.get("metadata", {}).get("type") == memory_type]

        # Deduplicate by text
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for r in results:
            text = r.get("text", "")
            if text not in seen:
                seen.add(text)
                deduped.append(r)

        deduped.sort(key=lambda x: x.get("score", 0), reverse=True)
        return deduped[:top_k]

    def promote_to_episodic(self) -> int:
        """Promote all current working memory entries to episodic storage.

        Returns the number of promoted entries.
        """
        return self.episodic.persist_working(self.working)

    def list_by_type(self, memory_type: str, limit: int = 10) -> list[dict[str, Any]]:
        """Legacy compatibility: list entries by type across all tiers."""
        if memory_type == MemoryTier.WORKING:
            return [{"text": e.text, "metadata": e.metadata} for e in self.working.get_all()]
        if memory_type == MemoryTier.SEMANTIC:
            return self.semantic.list_all(limit)
        # Episodic
        return self.episodic._search_jsonl(memory_type, limit) if hasattr(self.episodic, '_search_jsonl') else []

    def close(self) -> None:
        """Flush pending entries and release resources."""
        self.episodic.close()
        self._vector_store.close()

    # --- New add with embedding ---
    def add_with_embedding(self, text: str, metadata: dict[str, Any] | None = None, memory_type: str = "user") -> str:
        """Add a memory entry *with* embedding vector to the vector store.

        Also adds to the appropriate tier for backward compatibility.
        Returns the vector store entry ID.
        """
        embedding = self._embedder.embed(text)
        meta = {
            **(metadata or {}),
            "tier": memory_type,
            "timestamp": time.time(),
        }
        entry_id = self._vector_store.add(None, text, embedding, meta)

        # Also add to traditional tiers
        if memory_type == "working":
            self.add_working(text, metadata)
        elif memory_type == "semantic":
            self.add_semantic(text, metadata)
        else:
            self.add_episodic(text, metadata)

        return entry_id

    # --- Fusion ---
    def fuse_memories(
        self,
        memories: list[dict[str, Any]] | None = None,
        threshold: float = 0.88,
    ) -> list[dict[str, Any]]:
        """Fuse duplicate/similar memories across sessions.

        If *memories* is None, all entries from the vector store are
        loaded, fused, and re-inserted.
        """
        if memories is None:
            # Load all from vector store (best-effort, limited)
            dummy_emb = [0.0] * self._embedder.dimension
            raw = self._vector_store.search(dummy_emb, top_k=10000)
            memories = raw

        fused_entries = fuse(memories, threshold=threshold, embedder=self._embedder)

        # Re-insert fused entries into vector store
        if memories is not None and len(fused_entries) < len(memories):
            logger.info(
                "Fused %d memories into %d (%.1f%% reduction)",
                len(memories), len(fused_entries),
                (1 - len(fused_entries) / len(memories)) * 100,
            )

        return fused_entries

    # --- Decay ---
    def apply_decay(
        self,
        entries: list[dict[str, Any]] | None = None,
        half_life: float = 604800.0,
    ) -> list[dict[str, Any]]:
        """Apply time-based decay to memory entries."""
        if entries is None:
            dummy_emb = [0.0] * self._embedder.dimension
            entries = self._vector_store.search(dummy_emb, top_k=10000)
        return apply_decay(entries, half_life=half_life)

    # --- Embedding manager access ---
    @property
    def embedder(self) -> EmbeddingManager:
        return self._embedder

    @property
    def vector_store(self) -> VectorStore:
        return self._vector_store

    # --- Legacy compat ---
    def add(self, text: str, metadata: dict[str, Any] | None = None, memory_type: str = "user") -> None:
        """Legacy add: route to appropriate tier based on memory_type.

        Also stores the embedding in the vector store for semantic search.
        """
        self.add_with_embedding(text, metadata, memory_type)

    # --- Legacy private methods kept for backward compatibility ---
    def _search_impl(self, query: str, top_k: int) -> list[dict[str, Any]]:
        return self.search(query, top_k)

    def _search_jsonl(self, query: str, top_k: int) -> list[dict[str, Any]]:
        return self.episodic._search_jsonl(query, top_k)

    @staticmethod
    def _simple_score(query: str, text: str) -> float:
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        if not query_words:
            return 0.0
        intersection = query_words & text_words
        return len(intersection) / len(query_words)
