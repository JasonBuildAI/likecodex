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

    async def diagnose_error(
        self, command: str, error_output: str, working_dir: str | None = None
    ) -> str:
        """Diagnose command error and provide fix suggestion.

        Uses pattern matching for common errors and LLM for complex cases.

        Args:
            command: The command that was executed.
            error_output: The stderr output from the command.
            working_dir: Optional working directory for context.

        Returns:
            Diagnosis string with cause, fix, and optionally a suggested fix command.
        """
        if not error_output or not error_output.strip():
            return ""

        # 1. Try pattern-based diagnosis for common errors
        error_lower = error_output.lower()[:1000]

        # Command not found
        if any(
            kw in error_lower
            for kw in ["command not found", "not recognized", "is not recognized"]
        ):
            for line in error_output.split("\n"):
                if "not" in line.lower() and (
                    "command" in line.lower() or "recognized" in line.lower()
                ):
                    parts = line.strip().split("'")
                    cmd_name = parts[1] if len(parts) > 1 else "the command"
                    return (
                        f"❌ 命令未找到: '{cmd_name}' 未安装在系统中.\n"
                        f"💡 修复: 使用包管理器安装 (例如: npm install -g {cmd_name}, "
                        f"pip install {cmd_name}, apt install {cmd_name})"
                    )

        # Permission denied
        if "permission denied" in error_lower or "access is denied" in error_lower:
            return (
                f"❌ 权限被拒绝: 当前用户没有执行权限.\n"
                f"💡 修复: 使用 sudo (Unix) 或 以管理员身份运行 (Windows).\n"
                f"🔧 命令: sudo {command}"
            )

        # No such file or directory
        if "no such file" in error_lower or "file not found" in error_lower or "cannot find" in error_lower:
            return (
                f"❌ 文件或路径不存在.\n"
                f"💡 修复: 检查文件路径是否正确, 使用 'ls' 或 'dir' 查看当前目录内容."
            )

        # Python traceback
        if "traceback" in error_lower and "error" in error_lower:
            return (
                f"❌ Python 执行错误.\n"
                f"💡 修复: 检查代码语法和依赖. 使用 'pip list' 确认依赖已安装."
            )

        # npm/yarn errors
        if "npm err" in error_lower or "yarn" in error_lower:
            return (
                f"❌ npm/yarn 错误.\n"
                f"💡 修复: 尝试删除 node_modules 并重新安装: rm -rf node_modules && npm install"
            )

        # Git errors
        if "fatal:" in error_lower:
            if "not a git repository" in error_lower:
                return (
                    f"❌ 不是Git仓库.\n"
                    f"💡 修复: 使用 'git init' 初始化仓库或 'cd' 到正确的目录."
                )
            if "conflict" in error_lower:
                return (
                    f"❌ Git 合并冲突.\n"
                    f"💡 修复: 解决冲突文件后 git add, 然后 git commit."
                )

        # 2. Use LLM for complex/unrecognized errors
        prompt = f"""Analyze the following command execution error and provide a concise fix.

Command: {command}
Error output:
{error_output[:2000]}

Provide a structured diagnosis in this format:
[ERROR_CATEGORY] One-line category name
[CAUSE] Brief cause description
[FIX] Step-by-step fix suggestion
[FIX_CMD] If applicable, a single fix command (leave empty if N/A)

Respond in Chinese:"""

        from likecodex_engine.llm.base import Message, Role

        messages = [
            Message(
                role=Role.SYSTEM,
                content="You are a terminal error diagnostic expert. Provide concise, actionable fixes.",
            ),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            response = await self.llm.complete(
                messages, max_tokens=350, temperature=0.1
            )
            return response.content.strip()
        except Exception as exc:
            return f"诊断失败: {exc}"
