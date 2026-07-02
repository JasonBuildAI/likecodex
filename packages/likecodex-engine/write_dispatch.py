with open('d:\\App\\AgentProjects\\likecodex\\likecodex\\packages\\likecodex-engine\\likecodex_engine\\agent\\dispatch.py', 'w', encoding='utf-8') as f:
    f.write('''"""Parallel dispatch for read-only tool batches.

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

# Dedup cache: 5-second TTL for read-only tools
_dedup_cache: dict[str, tuple[float, str]] = {}
_DEDUP_TTL = 5.0

# Write tool dedup: 2-second TTL
_write_cache: dict[str, tuple[float, str, dict[str, Any]]] = {}
_WRITE_DEDUP_TTL = 2.0


def is_read_only_tool(name: str) -> bool:
    return name in READ_TOOLS or name.startswith("mcp__") or name.startswith("mcp_")


def _make_dedup_key(tool_name: str, arguments: dict[str, Any]) -> str:
    from likecodex_engine.context.utils import stable_json_dumps
    return f"{tool_name}:{stable_json_dumps(arguments)}"


def _merge_duplicate_calls(tool_calls: list[Any]) -> list[Any]:
    """Pre-merge identical tool calls within the same batch. Preserves order."""
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
    tool_calls = _merge_duplicate_calls(tool_calls)

    async def run_one(tc: Any) -> tuple[Any, str]:
        dedup_key = _make_dedup_key(tc.name, tc.arguments)

        if is_read_only_tool(tc.name):
            cached_dedup = _dedup_cache.get(dedup_key)
            if cached_dedup and (time.time() - cached_dedup[0]) < _DEDUP_TTL:
                return tc, cached_dedup[1]

        if not is_read_only_tool(tc.name):
            cached_write = _write_cache.get(dedup_key)
            if cached_write and (time.time() - cached_write[0]) < _WRITE_DEDUP_TTL:
                return tc, json.dumps({"merged": True, "previous_result": cached_write[1][:500]})

        if _tool_breaker.is_open(tc.name):
            return tc, json.dumps({
                "error": f"Tool '{tc.name}' is temporarily disabled (circuit breaker open)."
            })

        if is_read_only_tool(tc.name):
            cached = tool_cache.get(tc.name, tc.arguments)
            if cached is not None:
                return tc, cached

        timeout = TOOL_TIMEOUTS.get(tc.name, DEFAULT_TIMEOUT)
        try:
            result = await asyncio.wait_for(
                registry.execute(tc.name, tc.arguments),
                timeout=timeout,
            )
            _tool_breaker.record_success(tc.name)
        except asyncio.TimeoutError:
            result = json.dumps({"error": f"Tool '{tc.name}' timed out after {timeout}s."})
            _tool_breaker.record_failure(tc.name)
        except Exception as exc:
            result = json.dumps({"error": f"Tool '{tc.name}' failed: {exc}"})
            _tool_breaker.record_failure(tc.name)

        if is_read_only_tool(tc.name):
            tool_cache.set(tc.name, tc.arguments, result)
            _dedup_cache[dedup_key] = (time.time(), result)
        else:
            _write_cache[dedup_key] = (time.time(), result, tc.arguments)

        return tc, result

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
''')
print('Done')
