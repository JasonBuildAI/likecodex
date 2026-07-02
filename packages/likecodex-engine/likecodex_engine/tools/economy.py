"""Token economy system for tool usage cost tracking and budgeting."""

from __future__ import annotations

import json
import math
from typing import Any


_TOKEN_COST_TABLE: dict[str, int] = {
    # File system
    "read_file": 10,
    "write_file": 50,
    "list_dir": 5,
    "glob": 5,
    "search_files": 20,
    "move_file": 30,
    # Edit
    "edit_file": 60,
    "multi_edit": 80,
    "delete_range": 40,
    # Shell
    "run_command": 100,
    "bgjobs": 10,
    "bash_output": 10,
    "kill_shell": 10,
    # Search
    "grep_files": 15,
    "find_symbol": 10,
    "semantic_search": 30,
    "codegraph_search": 25,
    # Git
    "git_status": 10,
    "git_diff": 15,
    "git_log": 15,
    "git_commit": 60,
    # Web
    "web_search": 50,
    "web_fetch": 40,
    # Review
    "review_file": 80,
    "review_diff": 80,
    "check_dependencies": 60,
    # Test
    "discover_tests": 20,
    "run_tests": 150,
    "analyze_failures": 60,
    # Agent
    "task": 200,
    "parallel_tasks": 300,
    "run_skill": 150,
    # Memory
    "remember": 20,
    "forget": 10,
    "memory_search": 15,
    # Plan
    "todo_write": 10,
    "complete_step": 5,
    # History
    "history": 20,
    # LSP
    "lsp_definition": 10,
    "lsp_references": 15,
    "lsp_hover": 10,
    "lsp_diagnostics": 20,
    # Notebook
    "notebook_edit": 40,
    # Refactor
    "refactor_rename": 80,
    "refactor_extract": 100,
    # Session share
    "session_share": 10,
    "session_export": 15,
    "session_import": 20,
    # GitHub
    "github_create_pr": 40,
    "github_review_pr": 50,
    "github_add_pr_comment": 20,
    "github_create_issue": 30,
    "github_list_prs": 15,
    "github_list_issues": 15,
    # Profiler
    "profile_python": 100,
    "profile_function": 60,
    "memory_profile": 80,
    # Database
    "db_query": 40,
    "db_schema": 20,
    "db_explain": 15,
    "db_list_tables": 10,
    # Network
    "net_ping": 15,
    "net_dns_lookup": 10,
    "net_traceroute": 30,
    "net_http_headers": 15,
    "net_port_scan": 40,
    # Log analyzer
    "log_analyze": 30,
    "log_tail": 10,
    "log_grep": 25,
    "log_error_summary": 20,
    # API client
    "api_http_request": 30,
    "api_test": 80,
    "api_websocket_test": 40,
}

_DEFAULT_BUDGETS = {
    "full": 10_000_000,
    "economy": 50_000,
    "ultra_economy": 10_000,
}


class ToolEconomy:
    """Token economy system: budget tracking, cost estimation, and permission control.

    Modes:
      - full: No restrictions (default high budget).
      - economy: Conservative budget, hides expensive tools by default.
      - ultra_economy: Very restricted budget, only essential tools available.
    """

    def __init__(self, mode: str = "full", budget: int | None = None) -> None:
        self._mode = mode.lower()
        self._budget = budget or _DEFAULT_BUDGETS.get(self._mode, 50_000)
        self._used_tokens = 0
        self._tool_calls: list[dict[str, Any]] = []

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def token_budget(self) -> int:
        return self._budget

    @property
    def used_tokens(self) -> int:
        return self._used_tokens

    @property
    def remaining_tokens(self) -> int:
        return self._budget - self._used_tokens

    @property
    def usage_ratio(self) -> float:
        if self._budget <= 0:
            return 1.0
        return round(self._used_tokens / self._budget, 4)

    @staticmethod
    def estimate_tool_cost(tool_name: str, args: dict[str, Any] | None = None) -> int:
        """Estimate the token cost of a tool call based on tool name and arguments."""
        base = _TOKEN_COST_TABLE.get(tool_name, 30)

        if not args:
            return base

        args_cost = 0
        for key, value in args.items():
            if isinstance(value, str):
                args_cost += len(value) // 10  # ~10 chars = 1 token
            elif isinstance(value, (int, float)):
                args_cost += 2
            elif isinstance(value, (list, dict)):
                args_cost += len(str(value)) // 20
        return base + min(args_cost, base * 2)

    def record_call(self, tool_name: str, args: dict[str, Any] | None = None) -> int:
        """Record a tool call, deduct tokens, and return the estimated cost."""
        cost = self.estimate_tool_cost(tool_name, args)
        self._used_tokens += cost
        self._tool_calls.append({
            "tool": tool_name,
            "cost": cost,
            "running_total": self._used_tokens,
        })
        return cost

    def should_allow(self, tool_name: str, args: dict[str, Any] | None = None) -> bool:
        """Check whether a tool call should be allowed under current budget.

        In 'full' mode, always allows.
        In 'economy' / 'ultra_economy', checks remaining budget.
        """
        if self._mode == "full":
            return True

        cost = self.estimate_tool_cost(tool_name, args)
        return (self._used_tokens + cost) <= self._budget

    def get_status(self) -> dict[str, Any]:
        """Return the current economy status as a dict."""
        return {
            "mode": self._mode,
            "budget": self._budget,
            "used": self._used_tokens,
            "remaining": self.remaining_tokens,
            "usage_ratio": self.usage_ratio,
            "tool_calls": len(self._tool_calls),
        }

    @staticmethod
    def schema() -> dict[str, Any]:
        return {
            "description": "Tool economy system for token budgeting and cost estimation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["status", "estimate"],
                        "description": "Operation: status returns budget info; estimate estimates cost of a tool.",
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Tool name to estimate cost for",
                    },
                    "args": {
                        "type": "object",
                        "description": "Tool arguments for estimation",
                    },
                },
                "required": ["operation"],
            },
        }

    async def handle(self, operation: str, tool_name: str = "", args: dict[str, Any] | None = None) -> str:
        """Handle economy tool operations."""
        if operation == "status":
            return json.dumps(self.get_status())
        if operation == "estimate":
            cost = self.estimate_tool_cost(tool_name, args)
            allowed = self.should_allow(tool_name, args)
            return json.dumps({
                "tool": tool_name,
                "estimated_cost": cost,
                "allowed": allowed,
                "remaining": self.remaining_tokens,
            })
        return json.dumps({"error": f"Unknown operation: {operation}"})
