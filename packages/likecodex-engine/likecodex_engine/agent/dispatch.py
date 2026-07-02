"""Parallel dispatch for read-only tool batches."""

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

# Dedup cache: avoid re-executing identical read-only calls within the same batch
_dedup_cache: dict[str, tuple[float, str]] = {}  # key -> (timestamp, result)
_DEDUP_TTL = 1.0  # seconds


def is_read_only_tool(name: str) -> bool:
    return name in READ_TOOLS or name.startswith("mcp__") or name.startswith("mcp_")


async def execute_tool_calls_parallel(
    registry: ToolRegistry,
    tool_calls: list[Any],
) -> list[tuple[Any, str]]:
    """Execute read-only tools in parallel; others sequentially in order."""

    async def run_one(tc: Any) -> tuple[Any, str]:
        # Dedup check: identical read-only calls within 1s window
        if is_read_only_tool(tc.name):
            from likecodex_engine.context.utils import stable_json_dumps
            dedup_key = f"{tc.name}:{stable_json_dumps(tc.arguments)}"
            cached_dedup = _dedup_cache.get(dedup_key)
            if cached_dedup and (time.time() - cached_dedup[0]) < _DEDUP_TTL:
                return tc, cached_dedup[1]

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
            # Also update dedup cache
            from likecodex_engine.context.utils import stable_json_dumps
            dedup_key = f"{tc.name}:{stable_json_dumps(tc.arguments)}"
            _dedup_cache[dedup_key] = (time.time(), result)

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
