"""Parallel dispatch for read-only tool batches."""

from __future__ import annotations

import asyncio
from typing import Any

from likecodex_engine.tools.cache import READ_TOOLS, tool_cache
from likecodex_engine.tools.registry import ToolRegistry


def is_read_only_tool(name: str) -> bool:
    return name in READ_TOOLS or name.startswith("mcp__") or name.startswith("mcp_")


async def execute_tool_calls_parallel(
    registry: ToolRegistry,
    tool_calls: list[Any],
) -> list[tuple[Any, str]]:
    """Execute read-only tools in parallel; others sequentially in order."""

    async def run_one(tc: Any) -> tuple[Any, str]:
        # Check cache first for read-only tools
        if is_read_only_tool(tc.name):
            cached = tool_cache.get(tc.name, tc.arguments)
            if cached is not None:
                return tc, cached

        result = await registry.execute(tc.name, tc.arguments)

        # Cache read-only tool results
        if is_read_only_tool(tc.name):
            tool_cache.set(tc.name, tc.arguments, result)

        return tc, result

    # Invalidate cache when write tools are present
    for tc in tool_calls:
        if not is_read_only_tool(tc.name):
            tool_cache.invalidate()
            break

    if len(tool_calls) <= 1:
        results = []
        for tc in tool_calls:
            results.append(await run_one(tc))
        return results

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
