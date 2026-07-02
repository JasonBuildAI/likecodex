"""Terminal AI Assistant — natural language to shell command generation."""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Any


class TerminalAIAssistant:
    """AI assistant for terminal command generation and error diagnosis."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def suggest_command(
        self,
        description: str,
        os_type: str | None = None,
        working_dir: str | None = None,
    ) -> str:
        """Convert natural language description to shell command.

        Args:
            description: Natural language description of what to do.
            os_type: Target OS ("windows", "linux", "darwin"). Auto-detected if None.
            working_dir: Optional working directory for context-aware file listings.

        Returns:
            Suggested shell command string.
        """
        os_name = os_type or platform.system().lower()
        shell = "powershell" if "windows" in os_name else "bash"

        # Gather context if working_dir is provided
        context_lines = []
        if working_dir and os.path.isdir(working_dir):
            try:
                # List files in the directory (up to 30)
                files = os.listdir(working_dir)[:30]
                if files:
                    context_lines.append(f"Current directory files: {', '.join(files)}")

                # Check if it's a git repo
                git_dir = os.path.join(working_dir, ".git")
                if os.path.isdir(git_dir):
                    context_lines.append("This is a git repository.")
                    try:
                        result = subprocess.run(
                            ["git", "status", "--short"],
                            cwd=working_dir,
                            capture_output=True,
                            text=True,
                            timeout=3,
                        )
                        if result.stdout.strip():
                            context_lines.append(
                                f"Git status:\n{result.stdout.strip()}"
                            )
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        pass
            except PermissionError:
                pass

        context_str = "\n".join(context_lines)

        prompt = f"""You are a terminal command expert. Convert the user's natural language description into a {shell} command.

SAFETY RULES:
- NEVER suggest destructive commands (rm -rf /, format, dd, mkfs) unless explicitly described
- Prefer safe flags (-i for rm/cp/mv)
- For git operations, prefer --dry-run where available
- NEVER suggest commands that download and execute remote scripts

OUTPUT FORMAT:
- Return ONLY the command itself, no explanation, no markdown formatting
- Use command chaining (&&) for multi-step operations
- Prefer one-liners over scripts
- Escape special characters properly

CONTEXT:
{context_str}

User description: {description}

{shell} command:"""

        from likecodex_engine.llm.base import Message, Role

        messages = [
            Message(
                role=Role.SYSTEM,
                content="You are a shell command generator. Output only the command, nothing else. Follow safety rules strictly.",
            ),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            response = await self.llm.complete(
                messages, max_tokens=200, temperature=0.1
            )
            command = response.content.strip()
            # Remove markdown code fences if present
            if command.startswith("```"):
                lines = command.split("\n")
                command = (
                    "\n".join(lines[1:-1])
                    if lines[-1].startswith("```")
                    else "\n".join(lines[1:])
                )
            # Strip leading $ or > if present
            command = command.lstrip("$ >").strip()
            return command
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
