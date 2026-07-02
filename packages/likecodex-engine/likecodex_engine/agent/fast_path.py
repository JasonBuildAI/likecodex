"""Fast path optimization for common agent operations.

Bypasses the LLM for well-known, simple operations that can be executed
directly in <100ms. This reduces latency and token usage for routine tasks.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess  # noqa: S404 — controlled command execution
from dataclasses import dataclass, field
from typing import Any, Callable

from likecodex_engine.tools.registry import ToolRegistry

# Pattern-matching rules for fast-path detection
_FAST_PATH_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "read_file": [
        re.compile(r"^(?:read|open|show|display|查看|打开|显示)\s+(?:file\s+)?(?:`.+?`|\S+\.\w+)", re.IGNORECASE),
        re.compile(r"^(?:cat|type)\s+\S+", re.IGNORECASE),
    ],
    "list_dir": [
        re.compile(r"^(?:list|ls|dir|列出|查看目录)\s+(?:directory\s+)?\S+", re.IGNORECASE),
        re.compile(r"^what.*files.*in\s+\S+", re.IGNORECASE),
    ],
    "glob_search": [
        re.compile(r"^(?:find|search|glob|查找|搜索)\s+(?:files?\s+)?\S+", re.IGNORECASE),
        re.compile(r"^where.*file.*\*", re.IGNORECASE),
    ],
    "grep_search": [
        re.compile(r"^(?:grep|search|find|查找|搜索)\s+(?:for\s+)?['\"].+?['\"]", re.IGNORECASE),
    ],
    "git_status": [
        re.compile(r"^(?:git\s+)?status$", re.IGNORECASE),
        re.compile(r"^what.*changed", re.IGNORECASE),
        re.compile(r"^(?:check|show)\s+(?:git\s+)?status", re.IGNORECASE),
    ],
    "git_diff": [
        re.compile(r"^(?:git\s+)?diff\b", re.IGNORECASE),
        re.compile(r"^show.*(?:changes|diff|修改|变更)", re.IGNORECASE),
    ],
    "git_log": [
        re.compile(r"^(?:git\s+)?log\b", re.IGNORECASE),
        re.compile(r"^show.*(?:history|commit|提交|历史)", re.IGNORECASE),
    ],
}

# Tools that are safe for fast-path execution
_FAST_PATH_TOOLS = frozenset({
    "read_file",
    "list_dir",
    "glob",
    "grep_files",
    "git_status",
    "git_diff",
    "git_log",
})


@dataclass
class FastPathResult:
    """Result of a fast-path execution attempt."""

    handled: bool = False
    result: str = ""
    tool_name: str = ""
    elapsed_ms: float = 0.0


class FastPath:
    """Fast-path optimizer that intercepts common operations before LLM invocation.

    Detects simple, well-known operations from the prompt and executes them
    directly, bypassing the LLM entirely. Targets <100ms response time for
    basic file reads, directory listings, and git status checks.

    Usage::

        fast_path = FastPath(tool_registry)
        result = await fast_path.try_fast_path("read the file src/main.py")
        if result.handled:
            return result.result
        # else: fall through to normal LLM processing
    """

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        working_dir: str | None = None,
        enabled: bool = True,
    ) -> None:
        self._registry = tool_registry
        self._working_dir = working_dir or (tool_registry.working_dir if tool_registry else ".")
        self._enabled = enabled
        self._stats: dict[str, int] = {"attempts": 0, "hits": 0, "misses": 0}
        self._custom_handlers: dict[str, Callable[[str], str | None]] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def register_custom_handler(self, tool_name: str, handler: Callable[[str], str | None]) -> None:
        """Register a custom fast-path handler for a tool.

        The handler receives the raw prompt and should return a result string
        if it can handle it, or None to fall through.
        """
        self._custom_handlers[tool_name] = handler

    async def try_fast_path(self, prompt: str) -> FastPathResult:
        """Attempt to execute the prompt via fast path.

        Analyzes the prompt, matches it against known patterns,
        and executes the corresponding tool directly if matched.

        Returns FastPathResult with handled=True on success.
        """
        import time

        start = time.perf_counter()
        self._stats["attempts"] += 1

        if not self._enabled or not self._registry:
            result = FastPathResult()
            self._stats["misses"] += 1
            return result

        # Try custom handlers first
        for tool_name, handler in self._custom_handlers.items():
            try:
                custom_result = handler(prompt)
                if custom_result is not None:
                    self._stats["hits"] += 1
                    elapsed = (time.perf_counter() - start) * 1000
                    return FastPathResult(
                        handled=True,
                        result=custom_result,
                        tool_name=tool_name,
                        elapsed_ms=round(elapsed, 1),
                    )
            except Exception:
                continue

        # Match against known patterns
        for tool_name, patterns in _FAST_PATH_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(prompt.strip())
                if match:
                    result = await self._execute_fast_tool(tool_name, prompt, match)
                    if result.handled:
                        elapsed = (time.perf_counter() - start) * 1000
                        result.elapsed_ms = round(elapsed, 1)
                        self._stats["hits"] += 1
                        return result

        self._stats["misses"] += 1
        return FastPathResult()

    async def _execute_fast_tool(self, tool_name: str, prompt: str, match: re.Match[str]) -> FastPathResult:
        """Execute a matched tool via fast path."""
        if tool_name == "read_file":
            return await self._fast_read_file(prompt, match)
        if tool_name == "list_dir":
            return await self._fast_list_dir(prompt, match)
        if tool_name == "glob_search":
            return await self._fast_glob(prompt, match)
        if tool_name == "grep_search":
            return await self._fast_grep(prompt, match)
        if tool_name.startswith("git_"):
            return await self._fast_git(prompt, match)
        return FastPathResult()

    async def _fast_read_file(self, prompt: str, match: re.Match[str]) -> FastPathResult:
        """Fast file read: extract file path and read directly."""
        # Extract file path from backticks or as the last word
        path_match = re.search(r"`([^`]+)`", prompt)
        if not path_match:
            # Try to find a word with file extension
            path_match = re.search(r"(\S+\.\w+)", prompt)
        if not path_match:
            return FastPathResult()

        path = self._resolve_path(path_match.group(1))
        if not path or not path.exists() or not path.is_file():
            return FastPathResult()

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            if len(lines) > 500:
                content = "\n".join(lines[:500])
                content += f"\n\n... (truncated, {len(lines) - 500} more lines)"
            result = json.dumps({"path": str(path), "content": content, "line_count": len(lines)})
            return FastPathResult(handled=True, result=result, tool_name="read_file")
        except Exception as exc:
            return FastPathResult(handled=True, result=json.dumps({"error": str(exc)}), tool_name="read_file")

    async def _fast_list_dir(self, prompt: str, match: re.Match[str]) -> FastPathResult:
        """Fast directory listing."""
        path_match = re.search(r"`([^`]+)`", prompt) or re.search(r"(\S+)", prompt.split("list")[-1].strip())
        dir_path = self._resolve_path(path_match.group(1) if path_match else ".")
        if not dir_path or not dir_path.exists():
            return FastPathResult()

        try:
            entries = sorted(
                p.name + ("/" if p.is_dir() else "") for p in dir_path.iterdir()
            )
            result = json.dumps({"path": str(dir_path), "entries": entries, "count": len(entries)})
            return FastPathResult(handled=True, result=result, tool_name="list_dir")
        except Exception as exc:
            return FastPathResult(handled=True, result=json.dumps({"error": str(exc)}), tool_name="list_dir")

    async def _fast_glob(self, prompt: str, match: re.Match[str]) -> FastPathResult:
        """Fast glob search."""
        glob_match = re.search(r"`([^`]+)`", prompt) or re.search(r"\*(\S+)", prompt)
        if not glob_match:
            return FastPathResult()

        pattern = glob_match.group(0).strip("`").strip()
        if not pattern.startswith("**/"):
            pattern = f"**/{pattern}" if "*" in pattern else f"**/*{pattern}*"

        try:
            root = pathlib.Path(self._working_dir)
            matches = [str(p.relative_to(root)) for p in root.glob(pattern)][:100]
            result = json.dumps({"pattern": pattern, "matches": matches, "count": len(matches)})
            return FastPathResult(handled=True, result=result, tool_name="glob")
        except Exception as exc:
            return FastPathResult(handled=True, result=json.dumps({"error": str(exc)}), tool_name="glob")

    async def _fast_grep(self, prompt: str, match: re.Match[str]) -> FastPathResult:
        """Fast grep search using direct ripgrep if available, else fallback."""
        quoted = re.findall(r"['\"](.+?)['\"]", prompt[match.end():])
        search_term = quoted[0] if quoted else ""

        if not search_term:
            return FastPathResult()

        try:
            search_result = subprocess.run(  # noqa: S603 — trusted subprocess
                ["rg", "--no-heading", "-n", search_term, self._working_dir],
                capture_output=True, text=True, timeout=5,
            )
            lines = search_result.stdout.splitlines()[:50]
            result = json.dumps({"pattern": search_term, "matches": lines, "count": len(lines)})
            return FastPathResult(handled=True, result=result, tool_name="grep_files")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return FastPathResult()

    async def _fast_git(self, prompt: str, match: re.Match[str]) -> FastPathResult:
        """Fast git command execution."""
        text = prompt.strip().lower()

        try:
            cmd: list[str] = []

            if "status" in text or not any(x in text for x in ("diff", "log", "commit")):
                cmd = ["git", "-C", self._working_dir, "status", "--short"]
                tool = "git_status"
            elif "diff" in text:
                cmd = ["git", "-C", self._working_dir, "diff", "--stat"]
                tool = "git_diff"
            elif "log" in text or "history" in text or "commit" in text:
                cmd = ["git", "-C", self._working_dir, "log", "--oneline", "-20"]
                tool = "git_log"
            else:
                return FastPathResult()

            git_result = subprocess.run(  # noqa: S603 — trusted subprocess
                cmd, capture_output=True, text=True, timeout=5,
            )
            output = git_result.stdout or git_result.stderr
            result = json.dumps({"tool": tool, "output": output.strip()})
            return FastPathResult(handled=True, result=result, tool_name=tool)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return FastPathResult(handled=True, result=json.dumps({"error": str(exc)}), tool_name="git_status")

    def _resolve_path(self, raw_path: str) -> pathlib.Path | None:
        """Resolve a potentially relative path against working directory."""
        path = pathlib.Path(raw_path)
        if path.is_absolute():
            return path if path.exists() else None
        resolved = pathlib.Path(self._working_dir) / path
        return resolved if resolved.exists() else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "stats": self._stats,
            "patterns": {
                tool: [p.pattern for p in patterns]
                for tool, patterns in _FAST_PATH_PATTERNS.items()
            },
        }
