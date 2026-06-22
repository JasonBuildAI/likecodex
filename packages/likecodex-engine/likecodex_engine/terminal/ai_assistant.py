"""Terminal AI Assistant — natural language to shell command generation."""

from __future__ import annotations

import platform
from typing import Any


class TerminalAIAssistant:
    """AI assistant for terminal command generation and error diagnosis."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def suggest_command(self, description: str, os_type: str | None = None) -> str:
        """Convert natural language description to shell command."""
        os_name = os_type or platform.system().lower()
        shell = "powershell" if "windows" in os_name else "bash"

        prompt = f"""You are a terminal command expert. Convert the user's natural language description into a {shell} command.
Return ONLY the command itself, no explanation, no markdown formatting.

User description: {description}

Shell command:"""

        from likecodex_engine.llm.base import Message, Role

        messages = [
            Message(role=Role.SYSTEM, content="You are a shell command generator. Output only the command, nothing else."),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            response = await self.llm.complete(messages, max_tokens=100, temperature=0.1)
            command = response.content.strip()
            # Remove markdown code fences if present
            if command.startswith("```"):
                lines = command.split("\n")
                command = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
            return command.strip()
        except Exception as exc:
            return f"# Error generating command: {exc}"

    async def diagnose_error(self, command: str, error_output: str) -> str:
        """Diagnose command error and provide fix suggestion."""
        prompt = f"""Analyze the following command execution error and provide a fix.

Command: {command}
Error output:
{error_output[:2000]}

Provide:
1. Error cause (one sentence)
2. Fix suggestion (concise)

Response in Chinese:"""

        from likecodex_engine.llm.base import Message, Role

        messages = [
            Message(role=Role.SYSTEM, content="You are a terminal error diagnostic expert."),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            response = await self.llm.complete(messages, max_tokens=300, temperature=0.2)
            return response.content.strip()
        except Exception as exc:
            return f"诊断失败: {exc}"
