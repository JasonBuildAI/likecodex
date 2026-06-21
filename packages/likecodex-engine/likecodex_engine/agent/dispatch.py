"""Parallel dispatch for read-only tool batches."""

from __future__ import annotations

import asyncio
from typing import Any

from likecodex_engine.tools.registry import ToolRegistry

READ_ONLY_TOOLS = frozenset(
    {
        "read_file",
        "list_dir",
        "ls",
        "glob",
        "search_files",
        "grep_files",
        "find_symbol",
        "index_search",
        "codegraph_search",
        "codegraph_symbols",
        "codegraph_callers",
        "code_index",
        "git_status",
        "git_diff",
        "git_log",
        "git_branch",
        "lsp_definition",
        "lsp_references",
        "lsp_hover",
        "lsp_diagnostics",
        "history",
        "web_fetch",
    }
)


def is_read_only_tool(name: str) -> bool:
    return name in READ_ONLY_TOOLS or name.startswith("mcp__") or name.startswith("mcp_")


async def execute_tool_calls_parallel(
    registry: ToolRegistry,
    tool_calls: list[Any],
) -> list[tuple[Any, str]]:
    """Execute read-only tools in parallel; others sequentially in order."""

    async def run_one(tc: Any) -> tuple[Any, str]:
        result = await registry.execute(tc.name, tc.arguments)
        return tc, result

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
