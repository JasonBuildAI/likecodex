"""Parallel dispatch for read-only tool batches.

Enhanced dedup:
- Read-only dedup cache: 5-second TTL
- Write tool merge: detect and skip duplicate write calls
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from likecodex_engine.tools.cache import READ_TOOLS, tool_cache
from likecodex_engine.tools.registry import ToolRegistry

# Per-tool timeout configuration (seconds)
TOOL_TIMEOUTS: dict[str, float] = {
    "web_search": 15.0,
    "web_fetch": 15.0,
    "run_command": 120.0,
    "grep_files": 30.0,
    "codegraph_search": 5.0,
    "codegraph_reindex": 60.0,
}
DEFAULT_TIMEOUT = 30.0

# ── Simple in-memory circuit breaker for per-tool failure tracking ──────
class _ToolCircuitBreaker:
    """Tracks consecutive failures per tool and opens circuit after threshold."""
    def __init__(self, threshold: int = 3, cooldown: float = 30.0):
        self._threshold = threshold
        self._cooldown = cooldown
        self._failures: dict[str, list[float]] = {}

    def record_failure(self, tool_name: str) -> None:
        now = time.time()
        if tool_name not in self._failures:
            self._failures[tool_name] = []
        self._failures[tool_name] = [
            t for t in self._failures[tool_name] if now - t < self._cooldown
        ]
        self._failures[tool_name].append(now)

    def is_open(self, tool_name: str) -> bool:
        if tool_name not in self._failures:
            return False
        recent = [t for t in self._failures[tool_name] if time.time() - t < self._cooldown]
        return len(recent) >= self._threshold

    def record_success(self, tool_name: str) -> None:
        self._failures.pop(tool_name, None)

_tool_breaker = _ToolCircuitBreaker()

# Dedup cache: avoid re-executing identical read-only calls within 5s window
_dedup_cache: dict[str, tuple[float, str]] = {}  # key -> (timestamp, result)
_DEDUP_TTL = 5.0  # seconds
_DEDUP_MAX_ENTRIES = 1000  # prevent unbounded growth

# Write tool dedup: track identical write calls to merge/skip
_write_cache: dict[str, tuple[float, str, dict[str, Any]]] = {}
_WRITE_DEDUP_TTL = 2.0  # seconds
_WRITE_MAX_ENTRIES = 500  # prevent unbounded growth


def _evict_stale_cache(ttl: float, max_entries: int) -> None:
    """Periodically evict stale entries from dedup caches."""
    global _dedup_cache, _write_cache
    now = time.time()
    # Evict stale dedup entries
    stale_dedup = [k for k, (ts, _) in _dedup_cache.items() if now - ts > ttl]
    for k in stale_dedup:
        del _dedup_cache[k]
    # Trim dedup cache if over max
    if len(_dedup_cache) > _DEDUP_MAX_ENTRIES:
        sorted_dedup = sorted(_dedup_cache.items(), key=lambda x: x[1][0], reverse=True)
        _dedup_cache = dict(sorted_dedup[:_DEDUP_MAX_ENTRIES])
    # Evict stale write cache entries
    stale_write = [k for k, (ts, _, _) in _write_cache.items() if now - ts > ttl]
    for k in stale_write:
        del _write_cache[k]
    # Trim write cache if over max
    if len(_write_cache) > _WRITE_MAX_ENTRIES:
        sorted_write = sorted(_write_cache.items(), key=lambda x: x[1][0], reverse=True)
        _write_cache = dict(sorted_write[:_WRITE_MAX_ENTRIES])


def is_read_only_tool(name: str) -> bool:
    return name in READ_TOOLS or name.startswith("mcp__") or name.startswith("mcp_")


def _make_dedup_key(tool_name: str, arguments: dict[str, Any]) -> str:
    from likecodex_engine.context.utils import stable_json_dumps
    return f"{tool_name}:{stable_json_dumps(arguments)}"


def _merge_duplicate_calls(tool_calls: list[Any]) -> list[Any]:
    """Pre-merge identical tool calls within the same batch.
    
    For read-only tools: keep only the first occurrence.
    For write tools: keep only the first occurrence (they would produce same result).
    Returns deduplicated list while preserving order.
    """
    seen: set[str] = set()
    unique: list[Any] = []
    for tc in tool_calls:
        key = _make_dedup_key(tc.name, tc.arguments)
        if key in seen:
            continue
        seen.add(key)
        unique.append(tc)
    return unique


async def execute_tool_calls_parallel(
    registry: ToolRegistry,
    tool_calls: list[Any],
) -> list[tuple[Any, str]]:
    """Execute read-only tools in parallel; others sequentially in order."""

    # Periodic cache eviction (every 100 calls)
    _evict_stale_cache.counter = getattr(_evict_stale_cache, "counter", 0) + 1
    if _evict_stale_cache.counter >= 100:  # noqa: B018
        _evict_stale_cache(_DEDUP_TTL, _DEDUP_MAX_ENTRIES)
        _evict_stale_cache.counter = 0

    # Pre-merge duplicate calls within this batch
    tool_calls = _merge_duplicate_calls(tool_calls)

    async def run_one(tc: Any) -> tuple[Any, str]:
        dedup_key = _make_dedup_key(tc.name, tc.arguments)

        # Dedup check: identical read-only calls within 5s window
        if is_read_only_tool(tc.name):
            cached_dedup = _dedup_cache.get(dedup_key)
            if cached_dedup and (time.time() - cached_dedup[0]) < _DEDUP_TTL:
                return tc, cached_dedup[1]

        # Write tool merge: skip if identical write was just executed
        if not is_read_only_tool(tc.name):
            cached_write = _write_cache.get(dedup_key)
            if cached_write and (time.time() - cached_write[0]) < _WRITE_DEDUP_TTL:
                return tc, json.dumps({"merged": True, "previous_result": cached_write[1][:500]})

        # Circuit breaker check
        if _tool_breaker.is_open(tc.name):
            return tc, json.dumps({
                "error": f"Tool '{tc.name}' is temporarily disabled due to repeated failures. "
                         f"Circuit breaker is open (cooldown ~30s)."
            })

        # Check cache first for read-only tools
        if is_read_only_tool(tc.name):
            cached = tool_cache.get(tc.name, tc.arguments)
            if cached is not None:
                return tc, cached

        # Execute with timeout
        timeout = TOOL_TIMEOUTS.get(tc.name, DEFAULT_TIMEOUT)
        try:
            result = await asyncio.wait_for(
                registry.execute(tc.name, tc.arguments),
                timeout=timeout,
            )
            _tool_breaker.record_success(tc.name)
        except asyncio.TimeoutError:
            result = json.dumps({
                "error": f"Tool '{tc.name}' timed out after {timeout}s. "
                         f"The operation may still be running on the server."
            })
            _tool_breaker.record_failure(tc.name)
        except Exception as exc:
            result = json.dumps({"error": f"Tool '{tc.name}' failed: {exc}"})
            _tool_breaker.record_failure(tc.name)

        # Cache read-only tool results
        if is_read_only_tool(tc.name):
            tool_cache.set(tc.name, tc.arguments, result)
            _dedup_cache[dedup_key] = (time.time(), result)
        else:
            # Track write tools for merge detection
            _write_cache[dedup_key] = (time.time(), result, tc.arguments)

        return tc, result

    # Invalidate cache when write tools are present
    for tc in tool_calls:
        if not is_read_only_tool(tc.name):
            tool_cache.invalidate()
            break

    if len(tool_calls) <= 1:
        return [await run_one(tc) for tc in tool_calls]

    if all(is_read_only_tool(tc.name) for tc in tool_calls):
        return list(await asyncio.gather(*(run_one(tc) for tc in tool_calls)))

    results: list[tuple[Any, str]] = []
    batch: list[Any] = []
    for tc in tool_calls:
        if is_read_only_tool(tc.name):
            batch.append(tc)
        else:
            if batch:
                results.extend(await asyncio.gather(*(run_one(t) for t in batch)))
                batch = []
            results.append(await run_one(tc))
    if batch:
        results.extend(await asyncio.gather(*(run_one(t) for t in batch)))
    return results
