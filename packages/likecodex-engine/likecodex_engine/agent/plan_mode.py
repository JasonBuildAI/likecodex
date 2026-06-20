"""Plan mode: read-only exploration before execution."""

from __future__ import annotations

import json
from typing import Any

PLAN_MODE_DENIED_TOOLS = frozenset(
    {
        "write_file",
        "edit_file",
        "multi_edit",
        "move_file",
        "delete_range",
        "delete_symbol",
        "notebook_edit",
        "git_commit",
    }
)

PLAN_MODE_BASH_METACHARS = ("&&", "||", ">>", "<<", "$(", "`", ";", "|", ">", "<", "&", "\n", "\r")

PLAN_MODE_SAFE_BASH_PREFIXES = (
    "git status",
    "git diff",
    "git log",
    "git show",
    "git ls-files",
    "git grep",
    "git blame",
    "ls",
    "cat",
    "grep",
    "find",
    "head",
    "tail",
    "pwd",
    "echo",
    "wc",
    "which",
    "type",
    "uname",
    "hostname",
    "go version",
    "go list",
    "go doc",
    "go vet",
    "node -v",
    "npm list",
    "python --version",
    "pwsh -c get-",
    "powershell -c get-",
)


def is_plan_mode_denied_tool(tool_name: str) -> bool:
    return tool_name in PLAN_MODE_DENIED_TOOLS


def is_safe_plan_bash(command: str) -> bool:
    cmd = command.strip()
    lower = cmd.lower()
    for meta in PLAN_MODE_BASH_METACHARS:
        if meta in cmd:
            return False
    return any(lower == prefix or lower.startswith(prefix + " ") for prefix in PLAN_MODE_SAFE_BASH_PREFIXES)


def plan_mode_block_reason(tool_name: str, arguments: dict[str, Any]) -> str | None:
    if is_plan_mode_denied_tool(tool_name):
        return f"Plan mode blocks write tool `{tool_name}`. Exit plan mode before mutating files."
    if tool_name == "run_command":
        command = str(arguments.get("command", ""))
        if not is_safe_plan_bash(command):
            return (
                f"Plan mode blocks shell command (unsafe or side-effectful): {command[:120]}. "
                "Use read-only commands like git diff, grep, ls."
            )
    return None


def filter_tools_for_plan_mode(tool_names: list[str]) -> list[str]:
    return [n for n in tool_names if not is_plan_mode_denied_tool(n)]


def plan_mode_tool_result(tool_name: str, reason: str) -> str:
    return json.dumps({"error": reason, "plan_mode": True, "tool": tool_name})
