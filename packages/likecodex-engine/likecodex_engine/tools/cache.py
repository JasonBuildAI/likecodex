"""Tool result cache - avoid redundant execution of read-only tools."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any


class ToolResultCache:
    """LRU cache with TTL for tool results.

    Caches results of read-only tool calls so that repeated calls with
    the same arguments return instantly from cache.
    """

    def __init__(self, max_size: int = 100, default_ttl: float = 5.0) -> None:
        self._cache: OrderedDict[str, tuple[float, str, str]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl

    def _make_key(self, tool_name: str, args: dict[str, Any]) -> str:
        content = json.dumps({"name": tool_name, "args": args}, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, tool_name: str, args: dict[str, Any]) -> str | None:
        """Return cached result or None if not found/expired."""
        key = self._make_key(tool_name, args)
        if key not in self._cache:
            return None

        expire_at, result, _name = self._cache[key]
        if time.time() > expire_at:
            del self._cache[key]
            return None

        # LRU: move to end
        self._cache.move_to_end(key)
        return result

    def set(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: str,
        ttl: float | None = None,
    ) -> None:
        """Store a result in the cache."""
        key = self._make_key(tool_name, args)
        expire_at = time.time() + (ttl or self._default_ttl)

        self._cache[key] = (expire_at, result, tool_name)
        self._cache.move_to_end(key)

        # Evict oldest items if over max size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, tool_name: str | None = None) -> None:
        """Invalidate cached results.

        Args:
            tool_name: If provided, only invalidate tools with this name.
                       If None, invalidate everything.
        """
        if tool_name is None:
            self._cache.clear()
            return

        to_delete = [
            k
            for k, (_expire, _result, name) in self._cache.items()
            if name == tool_name
        ]
        for k in to_delete:
            del self._cache[k]


# Global singleton
tool_cache = ToolResultCache()

# Tool classification
READ_TOOLS = {
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
    "codegraph_viz",
    "git_status",
    "git_diff",
    "git_log",
    "git_branch",
    "lsp_hover",
    "lsp_diagnostics",
    "lsp_definition",
    "lsp_references",
    "web_search",
    "web_fetch",
    "bash_output",
    "deepseek_cache_analyze",
    "deepseek_reasoning",
    "deepseek_cost_estimate",
}

WRITE_TOOLS = {
    "write_file",
    "edit_file",
    "multi_edit",
    "move_file",
    "delete_range",
    "delete_symbol",
    "run_command",
    "kill_shell",
    "git_commit",
    "notebook_edit",
    "remember",
    "forget",
    "todo_write",
    "complete_step",
    "deepseek_switch_model",
}
