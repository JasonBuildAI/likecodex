"""Memory decay based on time and access frequency.

Long-unaccessed memories receive a lower priority score so that
fresh, frequently-accessed entries remain at the top of search results.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Default half-life in seconds (7 days)
_DEFAULT_HALF_LIFE = 7 * 24 * 3600.0


def apply_decay(
    entries: list[dict[str, Any]],
    half_life: float = _DEFAULT_HALF_LIFE,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Apply time-based and frequency-based decay to memory entries.

    Each entry's ``"score"`` is multiplied by a decay factor in [0, 1]
    computed as::

        age = now - last_access
        decay = 2 ** (-age / half_life)
        final_score = original_score * decay * frequency_boost

    where *frequency_boost* = 1 + log2(1 + access_count) / 10,
    so frequently-accessed memories decay more slowly.

    Parameters
    ----------
    entries:
        List of memory dicts. Each may contain ``"metadata"`` with keys
        ``"timestamp"`` (creation time), ``"last_access"`` (last access
        time), ``"access_count"`` (int).  If missing, sensible defaults
        are assumed.
    half_life:
        Half-life in seconds.  Defaults to 7 days.
    now:
        Reference time (seconds since epoch).  Defaults to
        :func:`time.time`.

    Returns
    -------
    list[dict]:
        Input entries with ``"score"`` modified in place.  Entries whose
        score drops below 0.01 are included but marked
        ``metadata.decayed = True``.
    """
    if not entries:
        return []

    now_ts = now if now is not None else time.time()

    for entry in entries:
        _apply_single_decay(entry, half_life, now_ts)

    # Sort by adjusted score descending
    entries.sort(key=lambda e: e.get("score", 0.0) if isinstance(e.get("score"), (int, float)) else 0.0, reverse=True)
    return entries


def _apply_single_decay(
    entry: dict[str, Any],
    half_life: float,
    now: float,
) -> None:
    """Apply decay to a single entry (mutates in place)."""
    meta = entry.get("metadata", {})
    if meta is None:
        meta = {}
        entry["metadata"] = meta

    original_score: float = entry.get("score", 0.0)
    if not isinstance(original_score, (int, float)):
        original_score = 0.0

    # --- Last access time ---
    last_access = meta.get("last_access", meta.get("timestamp", now))
    if not isinstance(last_access, (int, float)):
        last_access = now

    age = max(0.0, now - last_access)

    # --- Access count ---
    access_count = meta.get("access_count", 1)
    if not isinstance(access_count, (int, float)):
        access_count = 1
    access_count = max(1, int(access_count))

    # --- Decay factor ---
    # Exponentially decaying weight
    decay_weight = 2.0 ** (-age / half_life)

    # Frequency boost: heavily accessed memories decay slower
    frequency_boost = 1.0 + (access_count ** 0.3) / 20.0

    adjusted = original_score * decay_weight * frequency_boost

    # Clamp
    adjusted = max(0.0, min(1.0, adjusted))

    entry["score"] = round(adjusted, 6)
    meta["decay_raw_score"] = round(original_score, 6)
    meta["decay_weight"] = round(decay_weight, 6)
    meta["decay_boost"] = round(frequency_boost, 6)
    meta["decayed"] = adjusted < 0.01


def update_access(entry: dict[str, Any]) -> None:
    """Update the access metadata for an entry (mutates in place).

    Call this when a memory is retrieved/accessed to bump its
    ``last_access`` and ``access_count``.
    """
    meta = entry.setdefault("metadata", {})
    if meta is None:
        meta = {}
        entry["metadata"] = meta
    meta["last_access"] = time.time()
    meta["access_count"] = meta.get("access_count", 0) + 1
