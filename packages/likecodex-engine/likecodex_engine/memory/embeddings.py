"""Embedding manager with multi-backend support.

Supports three backends, auto-detected with graceful degradation:
1. sentence-transformers (preferred - local, fast, offline-capable)
2. OpenAI embeddings (fallback - requires API key)
3. TF-IDF (last resort - no dependencies needed)
"""

from __future__ import annotations

import logging
import math
import re
import time
from collections import Counter, OrderedDict
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LRU Cache
# ---------------------------------------------------------------------------

class LRUCache:
    """Simple LRU cache with max size."""

    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._cache: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)


# ---------------------------------------------------------------------------
# TF-IDF embedding backend (zero-dependency fallback)
# ---------------------------------------------------------------------------

class TfidfEmbedder:
    """Simple TF-IDF vectorizer that produces fixed-dimension embeddings.

    Dimension is determined by vocabulary size up to max_features.
    Vectors are L2-normalized.
    """

    def __init__(self, max_features: int = 512) -> None:
        self._max_features = max_features
        self._vocab: dict[str, int] = {}
        self._idf: dict[int, float] = {}
        self._doc_count = 0
        self._dims = max_features

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
        return tokens

    def _get_embedding_dim(self) -> int:
        return self._dims

    def embed(self, text: str) -> list[float]:
        """Compute a TF-IDF style embedding for a single text."""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self._dims

        # Build local term frequency
        tf = Counter(tokens)
        max_tf = max(tf.values())

        vec = [0.0] * self._dims
        for token, count in tf.items():
            if token not in self._vocab:
                # Assign new index on first encounter
                idx = len(self._vocab)
                if idx >= self._dims:
                    # Use hash-based fallback
                    idx = abs(hash(token)) % self._dims
                self._vocab[token] = idx
            idx = self._vocab[token]
            # Normalized TF * IDF
            tf_val = count / max_tf
            idf_val = self._idf.get(idx, 1.0)
            vec[idx] = tf_val * idf_val

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def partial_fit(self, texts: list[str]) -> None:
        """Update IDF vocabulary with new documents."""
        for text in texts:
            tokens = set(self._tokenize(text))
            for token in tokens:
                if token not in self._vocab:
                    idx = len(self._vocab)
                    if idx >= self._dims:
                        idx = abs(hash(token)) % self._dims
                    self._vocab[token] = idx
            self._doc_count += 1

        # Recompute IDF
        n = self._doc_count
        for idx in self._vocab.values():
            self._idf[idx] = math.log((1 + n) / (1 + 1)) + 1  # smooth IDF


# ---------------------------------------------------------------------------
# Embedding Manager
# ---------------------------------------------------------------------------

class EmbeddingManager:
    """Unified embedding manager with automatic backend detection and fallback.

    Backend priority:
      1. sentence-transformers (local, offline, best quality)
      2. OpenAI ``text-embedding-3-small`` (requires env OPENAI_API_KEY)
      3. TF-IDF (zero dependencies, always available)

    Usage::

        emb = EmbeddingManager()
        vector = emb.embed("some text")
        batch = emb.embed_batch(["text1", "text2"])
    """

    def __init__(
        self,
        preferred: str = "auto",
        cache_size: int = 1000,
        openai_model: str = "text-embedding-3-small",
        tfidf_max_features: int = 512,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            preferred: Backend name (``"auto"``, ``"sentence-transformers"``,
                       ``"openai"``, ``"tfidf"``).
            cache_size: Max LRU cache entries (0 to disable).
            openai_model: OpenAI model name for embeddings.
            tfidf_max_features: Max dimensions for TF-IDF fallback.
            **kwargs: Extra arguments passed to the backend constructor.
        """
        self._cache = LRUCache(cache_size) if cache_size > 0 else None
        self._backend_name: str = preferred
        self._openai_model = openai_model
        self._backend: TfidfEmbedder | Any = None  # will be set by _init_backend
        self._kwargs = kwargs
        self._init_backend()

    # ------------------------------------------------------------------
    # Backend initialisation
    # ------------------------------------------------------------------

    def _init_backend(self) -> None:
        """Detect and initialise the best available backend."""
        if self._backend_name != "auto":
            self._backend = self._load_named_backend(self._backend_name)
            if self._backend is not None:
                logger.info("Embedding backend: %s (user-requested)", self._backend_name)
                return
            logger.warning("Requested backend %r unavailable, falling back", self._backend_name)

        # Auto-detect (best → worst)
        for name in ("sentence-transformers", "openai", "tfidf"):
            backend = self._load_named_backend(name)
            if backend is not None:
                self._backend = backend
                self._backend_name = name
                logger.info("Embedding backend: %s (auto-detected)", name)
                return

        # Should never reach here – tfidf is always available
        self._backend = TfidfEmbedder(max_features=self._kwargs.get("tfidf_max_features", 512))
        self._backend_name = "tfidf"
        logger.info("Embedding backend: tfidf (final fallback)")

    def _load_named_backend(self, name: str) -> Any | None:
        """Try to load a backend by name. Returns None on failure."""
        try:
            if name == "sentence-transformers":
                return self._load_sentence_transformers()
            if name == "openai":
                return self._load_openai()
            if name == "tfidf":
                return TfidfEmbedder(max_features=self._kwargs.get("tfidf_max_features", 512))
        except Exception as exc:
            logger.debug("Failed to load backend %r: %s", name, exc)
            return None
        return None

    def _load_sentence_transformers(self) -> Any:
        """Load and return a sentence-transformers model wrapper."""
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer

            model_name = self._kwargs.get("st_model", "all-MiniLM-L6-v2")
            model = SentenceTransformer(model_name)

            class STBackend:
                def __init__(self, m: Any) -> None:
                    self._model = m
                    self._np = __import__("numpy")

                def embed(self, text: str) -> list[float]:
                    vec = self._model.encode(text, normalize_embeddings=True)
                    return vec.tolist()

                def embed_batch(self, texts: list[str]) -> list[list[float]]:
                    vecs = self._model.encode(texts, normalize_embeddings=True)
                    return vecs.tolist()

            return STBackend(model)
        except ImportError:
            raise

    def _load_openai(self) -> Any | None:
        """Load and return an OpenAI embedding wrapper."""
        import os

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.debug("OPENAI_API_KEY not set, skipping OpenAI backend")
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            model = self._openai_model

            class OpenAIBackend:
                def __init__(self, c: Any, m: str) -> None:
                    self._client = c
                    self._model = m

                def embed(self, text: str) -> list[float]:
                    # Replace newlines for API compatibility
                    resp = self._client.embeddings.create(
                        input=text.replace("\n", " "), model=self._model
                    )
                    return resp.data[0].embedding

                def embed_batch(self, texts: list[str]) -> list[list[float]]:
                    sanitized = [t.replace("\n", " ") for t in texts]
                    resp = self._client.embeddings.create(
                        input=sanitized, model=self._model
                    )
                    # Sort by index to preserve ordering
                    sorted_data = sorted(resp.data, key=lambda x: x.index)
                    return [d.embedding for d in sorted_data]

            return OpenAIBackend(client, model)
        except ImportError:
            logger.debug("openai package not installed, skipping OpenAI backend")
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def backend_name(self) -> str:
        """Name of the currently active backend."""
        return self._backend_name

    @property
    def dimension(self) -> int:
        """Detect embedding dimension (heuristic – embeds a dummy string)."""
        dummy = self.embed("dimension probe")
        return len(dummy)

    def embed(self, text: str) -> list[float]:
        """Compute embedding vector for a single text.

        Results are cached in an LRU cache (if enabled).
        """
        if self._cache is not None:
            cached = self._cache.get(text)
            if cached is not None:
                return cached

        vector = self._backend.embed(text)

        if self._cache is not None:
            self._cache.put(text, vector)
        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Compute embedding vectors for a batch of texts.

        Batches that are fully cached will be served from cache.
        """
        if self._cache is None or not texts:
            return self._backend.embed_batch(texts)

        uncached: list[tuple[int, str]] = []
        results: list[list[float] | None] = [None] * len(texts)

        for i, t in enumerate(texts):
            cached = self._cache.get(t)
            if cached is not None:
                results[i] = cached
            else:
                uncached.append((i, t))

        if uncached:
            uncached_texts = [t for _, t in uncached]
            vectors = self._backend.embed_batch(uncached_texts)
            for (idx, text), vec in zip(uncached, vectors, strict=False):
                self._cache.put(text, vec)
                results[idx] = vec

        return [r for r in results if r is not None]  # type: ignore[misc]

    def clear_cache(self) -> None:
        """Clear the embedding LRU cache."""
        if self._cache is not None:
            self._cache = LRUCache(self._cache._maxsize)

    def similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two texts."""
        vec_a = self.embed(text_a)
        vec_b = self.embed(text_b)
        return self._cosine_sim(vec_a, vec_b)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
