"""Shell execution tools for the agent."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


class ShellTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    def run_command_schema(self) -> dict[str, Any]:
        return {
            "description": "Run a shell command in the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 120)",
                    },
                },
                "required": ["command"],
            },
        }

    def _shell_command(self, command: str) -> tuple[str, list[str]]:
        if sys.platform == "win32":
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            return comspec, ["/c", command]
        return "sh", ["-c", command]

    async def run_command(self, command: str, timeout: int = 120) -> str:
        executable, args = self._shell_command(command)
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                *args,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=float(timeout))
            return json.dumps(
                {
                    "command": command,
                    "exit_code": proc.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                }
            )
        except TimeoutError:
            if proc is not None and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return json.dumps(
                {
                    "command": command,
                    "exit_code": None,
                    "stdout": "",
                    "stderr": "Command timed out",
                    "timed_out": True,
                }
            )
        except Exception as e:
            if proc is not None and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return json.dumps({"command": command, "error": str(e)})
