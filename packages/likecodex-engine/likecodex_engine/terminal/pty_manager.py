"""Terminal Manager — manages shell sessions via subprocess.

Provides per-session command execution with streaming output via SSE.
Supports Windows (PowerShell) and Unix (bash) platforms.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TerminalSession:
    """A single terminal session."""

    id: str
    cwd: str
    shell: str
    history: list[dict[str, str]] = field(default_factory=list)
    _proc: Any = None

    def __post_init__(self) -> None:
        if not self.shell:
            if sys.platform == "win32":
                self.shell = "powershell.exe"
            else:
                self.shell = "/bin/bash"


class TerminalManager:
    """Manages terminal sessions."""

    def __init__(self, working_dir: str = ".") -> None:
        self.working_dir = str(os.path.resolve(working_dir))
        self._sessions: dict[str, TerminalSession] = {}
        self._shell = self._detect_shell()

    @staticmethod
    def _detect_shell() -> str:
        if sys.platform == "win32":
            return "powershell.exe"
        return os.environ.get("SHELL", "/bin/bash")

    def create_session(self, session_id: str, cwd: str | None = None) -> TerminalSession:
        """Create a new terminal session."""
        session = TerminalSession(
            id=session_id,
            cwd=cwd or self.working_dir,
            shell=self._shell,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> TerminalSession | None:
        """Get a terminal session by ID."""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        """Close a terminal session."""
        session = self._sessions.pop(session_id, None)
        if session and session._proc and not session._proc.returncode:
            try:
                session._proc.kill()
            except (ProcessLookupError, OSError):
                pass
        return session is not None

    async def execute_command(
        self,
        session_id: str,
        command: str,
    ) -> dict[str, Any]:
        """Execute a command and return the output.

        This runs a single command (not a persistent shell), which is
        simpler and safer than maintaining a PTY.
        """
        session = self._sessions.get(session_id)
        if not session:
            session = self.create_session(session_id)

        try:
            # Build command arguments
            if sys.platform == "win32":
                args = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ]
            else:
                args = ["/bin/bash", "-c", command]

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=session.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "TERM": "xterm-256color"},
            )

            stdout, stderr = await proc.communicate()

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            result = {
                "command": command,
                "output": output,
                "error": error,
                "exitCode": proc.returncode or 0,
                "cwd": session.cwd,
            }

            # Update cwd if command was 'cd'
            if command.strip().startswith("cd "):
                new_dir = command.strip()[3:].strip()
                new_cwd = os.path.join(session.cwd, new_dir)
                if os.path.isdir(new_cwd):
                    session.cwd = os.path.abspath(new_cwd)
                    result["cwd"] = session.cwd

            session.history.append({
                "command": command,
                "output": output + error,
            })

            return result

        except Exception as exc:
            return {
                "command": command,
                "output": "",
                "error": str(exc),
                "exitCode": 1,
                "cwd": session.cwd,
            }

    async def execute_command_stream(
        self,
        session_id: str,
        command: str,
    ):
        """Execute a command and yield output lines as they arrive.

        Yields dicts: {"type": "output", "content": "..."} or
        {"type": "error", "content": "..."} or {"type": "done", "exitCode": N}
        """
        session = self._sessions.get(session_id)
        if not session:
            session = self.create_session(session_id)

        try:
            if sys.platform == "win32":
                args = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ]
            else:
                args = ["/bin/bash", "-c", command]

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=session.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "TERM": "xterm-256color"},
            )

            # Read stdout and stderr concurrently
            async def read_stream(stream, output_type):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    yield {
                        "type": output_type,
                        "content": line.decode("utf-8", errors="replace"),
                    }

            # Yield from both streams
            stdout_task = asyncio.create_task(
                self._collect_lines(proc.stdout, "output")
            )
            stderr_task = asyncio.create_task(
                self._collect_lines(proc.stderr, "error")
            )

            stdout_lines = await stdout_task
            stderr_lines = await stderr_task
            await proc.wait()

            for item in stdout_lines:
                yield item
            for item in stderr_lines:
                yield item

            yield {"type": "done", "exitCode": proc.returncode or 0}

        except Exception as exc:
            yield {"type": "error", "content": str(exc)}
            yield {"type": "done", "exitCode": 1}

    @staticmethod
    async def _collect_lines(stream, output_type: str) -> list[dict[str, str]]:
        """Collect all lines from a stream."""
        results: list[dict[str, str]] = []
        while True:
            line = await stream.readline()
            if not line:
                break
            results.append({
                "type": output_type,
                "content": line.decode("utf-8", errors="replace"),
            })
        return results
