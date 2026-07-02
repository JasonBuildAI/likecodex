"""Cross-session memory fusion.

Detects duplicate / highly-similar memories across sessions and merges
them into a single consolidated entry (keeping the latest timestamp and
merging metadata).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .embeddings import EmbeddingManager

logger = logging.getLogger(__name__)

# Similarity threshold above which two entries are considered "same"
_DEFAULT_SIMILARITY_THRESHOLD = 0.88


def fuse(
    memories: list[dict[str, Any]],
    threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
    embedder: EmbeddingManager | None = None,
) -> list[dict[str, Any]]:
    """Fuse a list of memory entries by merging duplicates / near-duplicates.

    Two entries are considered duplicates when their embedding cosine
    similarity exceeds *threshold*.

    Parameters
    ----------
    memories:
        List of memory dicts. Each dict must contain at least a ``"text"``
        key and may optionally contain ``"metadata"`` (dict) and
        ``"embedding"`` (list[float]) keys.
    threshold:
        Cosine similarity threshold (0‑1). Entries with similarity >= this
        value will be merged.
    embedder:
        :class:`EmbeddingManager` instance for computing text embeddings.
        If *None*, a default one will be created.  When entries already
        carry an ``"embedding"`` key, it is used directly.

    Returns
    -------
    list[dict]:
        Fused memory entries, sorted by ``"score"`` descending.
    """
    if not memories:
        return []

    if embedder is None:
        embedder = EmbeddingManager(cache_size=0)

    # 1. Ensure every entry has an embedding
    for entry in memories:
        if "embedding" not in entry or entry["embedding"] is None:
            entry["embedding"] = embedder.embed(entry.get("text", ""))

    # 2. Greedy clustering
    clusters: list[list[dict[str, Any]]] = []
    assigned: set[int] = set()

    for i, entry in enumerate(memories):
        if i in assigned:
            continue
        cluster = [entry]
        assigned.add(i)
        emb_i = entry["embedding"]

        for j, other in enumerate(memories):
            if j in assigned:
                continue
            emb_j = other["embedding"]
            sim = EmbeddingManager._cosine_sim(emb_i, emb_j)
            if sim >= threshold:
                cluster.append(other)
                assigned.add(j)

        clusters.append(cluster)

    # 3. Merge each cluster into a single entry
    fused: list[dict[str, Any]] = []
    for cluster in clusters:
        if len(cluster) == 1:
            fused.append(cluster[0])
        else:
            fused.append(_merge_cluster(cluster))

    # 4. Sort by score (descending), with score defaulting to 0
    fused.sort(key=lambda e: e.get("score", 0.0) if isinstance(e.get("score"), (int, float)) else 0.0, reverse=True)
    return fused


def _merge_cluster(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a cluster of similar entries into one consolidated entry."""
    # Sort by timestamp (descending) so the latest entry is primary
    sorted_cluster = sorted(
        cluster,
        key=lambda e: _get_timestamp(e),
        reverse=True,
    )

    primary = dict(sorted_cluster[0])
    merged_meta: dict[str, Any] = {}
    seen_sources: set[str] = set()
    all_texts: list[str] = []
    max_score = 0.0

    for entry in sorted_cluster:
        # Metadata merge (later entries don't overwrite earlier keys)
        meta = entry.get("metadata", {}) or {}
        for k, v in meta.items():
            if k not in merged_meta:
                merged_meta[k] = v
        # Track sources
        src = meta.get("source_session", "")
        if src:
            seen_sources.add(src)
        # Track unique text snippets
        txt = entry.get("text", "")
        if txt and txt not in all_texts:
            all_texts.append(txt)
        # Best score
        score = entry.get("score", 0.0)
        if isinstance(score, (int, float)) and score > max_score:
            max_score = score

    merged_meta["merged_from_sessions"] = list(seen_sources)
    merged_meta["merged_count"] = len(cluster)
    merged_meta["fused_at"] = time.time()

    primary["metadata"] = merged_meta
    primary["text"] = all_texts[0] if all_texts else primary.get("text", "")
    primary["score"] = max_score
    primary["_fused"] = True

    return primary


def _get_timestamp(entry: dict[str, Any]) -> float:
    """Extract timestamp from an entry (metadata or top-level)."""
    meta = entry.get("metadata", {}) or {}
    ts = meta.get("timestamp", meta.get("stored_at", 0.0))
    if isinstance(ts, (int, float)):
        return ts
    try:
        return float(ts)
    except (ValueError, TypeError):
        return 0.0
