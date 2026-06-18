"""Tool registry and dispatch."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from likecodex_engine.tools.code_review import CodeReviewTools
from likecodex_engine.tools.code_search import CodeSearchTools
from likecodex_engine.tools.filesystem import FileSystemTools
from likecodex_engine.tools.git import GitTools
from likecodex_engine.tools.shell import ShellTools


class ToolRegistry:
    """Registers tools and dispatches calls."""

    def __init__(self, working_dir: str | None = None) -> None:
        self.working_dir = working_dir or "."
        self._tools: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[..., Awaitable[str]]] = {}

        # Register built-in tools
        fs = FileSystemTools(self.working_dir)
        self.register("read_file", fs.read_file_schema(), fs.read_file)
        self.register("write_file", fs.write_file_schema(), fs.write_file)
        self.register("list_dir", fs.list_dir_schema(), fs.list_dir)
        self.register("search_files", fs.search_files_schema(), fs.search_files)

        shell = ShellTools(self.working_dir)
        self.register("run_command", shell.run_command_schema(), shell.run_command)

        search = CodeSearchTools(self.working_dir)
        self.register("grep_files", search.grep_schema(), search.grep_files)
        self.register("find_symbol", search.find_symbol_schema(), search.find_symbol)
        self.register("index_search", search.index_search_schema(), search.index_search)

        git = GitTools(self.working_dir)
        self.register("git_status", git.status_schema(), git.git_status)
        self.register("git_diff", git.diff_schema(), git.git_diff)
        self.register("git_log", git.log_schema(), git.git_log)
        self.register("git_branch", git.branch_schema(), git.git_branch)
        self.register("git_commit", git.commit_schema(), git.git_commit)

        review = CodeReviewTools(self.working_dir)
        self.register("review_file", review.review_file_schema(), review.review_file)
        self.register("review_diff", review.review_diff_schema(), review.review_diff)
        self.register("check_dependencies", review.check_dependencies_schema(), review.check_dependencies)

    def register(
        self,
        name: str,
        schema: dict[str, Any],
        handler: Callable[..., Awaitable[str]],
    ) -> None:
        self._tools[name] = schema
        self._handlers[name] = handler

    def to_openai_schema(self) -> list[dict[str, Any]]:
        return [
            {"type": "function", "function": {"name": name, **schema}}
            for name, schema in sorted(self._tools.items(), key=lambda item: item[0])
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        handler = self._handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Tool '{name}' not found"})
        try:
            return await handler(**arguments)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
