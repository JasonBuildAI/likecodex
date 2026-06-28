"""Risk classification for tool invocations."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskClassifier:
    """Classifies the risk of a tool invocation based on rules and heuristics."""

    HIGH_RISK_PATTERNS = [
        "rm -rf",
        "format",
        "dd ",
        "mkfs",
        "> /dev",
        ":(){ :|:& };:",
        "curl",
        "wget",
        "fetch",
        "ssh",
        "scp",
        "nc ",
        "netcat",
        "python -m http.server",
        "openssl",
        "~/.ssh",
        "~/.aws",
        "~/.gnupg",
        "/etc/",
        "/sys/",
        "/proc/",
        "sudo",
        "powershell -enc",
        "Invoke-Expression",
        "iex ",
    ]

    MEDIUM_RISK_COMMANDS = [
        "pip install",
        "npm install",
        "npm ci",
        "cargo install",
        "apt ",
        "brew ",
        "choco ",
        "git push",
        "git reset --hard",
    ]

    READ_ONLY_TOOLS = {"read_file", "list_dir", "search_files", "git_status", "git_diff", "git_log", "git_branch"}

    @classmethod
    def classify_tool_call(cls, name: str, arguments: dict[str, Any]) -> RiskLevel:
        if name in cls.READ_ONLY_TOOLS:
            return RiskLevel.LOW
        if name == "run_command":
            return cls.classify_command(arguments.get("command", ""))
        return RiskLevel.MEDIUM

    @classmethod
    def classify_command(cls, command: str) -> RiskLevel:
        command_lower = command.lower()
        for pattern in cls.HIGH_RISK_PATTERNS:
            if pattern.lower() in command_lower:
                return RiskLevel.HIGH
        for pattern in cls.MEDIUM_RISK_COMMANDS:
            if pattern.lower() in command_lower:
                return RiskLevel.MEDIUM
        return RiskLevel.LOW
