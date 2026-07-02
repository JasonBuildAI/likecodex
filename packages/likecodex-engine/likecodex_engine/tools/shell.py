"""Shell execution tools for the agent, including background jobs."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


# ── Rust executor fallback detection ──────────────────────────


def _find_rust_executor() -> str | None:
    """Detect if the Rust CLI executor (likecodex-server) is available.

    Checks:
    1. likecodex in PATH (Rust binary)
    2. likecodex-server.exe in common locations
    3. cargo-built binary in workspace target directory

    Returns:
        Path to the Rust executor binary, or None if not found.
    """
    # Check PATH
    rust_binary = shutil.which("likecodex")
    if rust_binary:
        return rust_binary

    # Check common install locations
    home = Path.home()
    candidates = [
        home / ".cargo" / "bin" / "likecodex.exe",
        home / ".cargo" / "bin" / "likecodex",
        home / ".likecodex" / "install" / "target" / "debug" / "likecodex-server.exe",
        home / ".likecodex" / "install" / "target" / "release" / "likecodex-server.exe",
    ]
    if sys.platform != "win32":
        candidates = [p.with_suffix("") for p in candidates]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Check workspace target directory
    try:
        cwd = Path.cwd()
        for parent in (cwd, *cwd.parents):
            target_dir = parent / "target"
            if target_dir.exists():
                for sub in ("debug", "release"):
                    binary = target_dir / sub / "likecodex-server"
                    if sys.platform == "win32":
                        binary = binary.with_suffix(".exe")
                    if binary.exists():
                        return str(binary)
    except Exception:
        pass

    return None


def rust_executor_available() -> bool:
    """Check if the Rust executor is available for shell operations.

    Returns True if the Rust CLI binary is found, False otherwise.
    """
    return _find_rust_executor() is not None


def execute_shell_with_rust(command: str, working_dir: str, timeout: int = 120) -> dict:
    """Execute a shell command using the Rust executor binary.

    Falls back to Python subprocess if the Rust executor is not found.
    """
    executor = _find_rust_executor()
    if executor is None:
        return execute_shell_with_python(command, working_dir, timeout)

    try:
        result = subprocess.run(
            [executor, "exec", "--", command],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": "Command timed out",
            "timed_out": True,
        }
    except Exception as e:
        # Fallback to Python on any error
        return execute_shell_with_python(command, working_dir, timeout)


def execute_shell_with_python(command: str, working_dir: str, timeout: int = 120) -> dict:
    """Execute a shell command using Python subprocess (pure Python fallback)."""
    try:
        result = subprocess.run(
            command,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": "Command timed out",
            "timed_out": True,
        }
    except Exception as e:
        return {"command": command, "error": str(e)}


class BackgroundJob:
    """Tracks a long-running command started in the background."""

    def __init__(self, job_id: str, command: str) -> None:
        self.job_id = job_id
        self.command = command
        self.proc: asyncio.subprocess.Process | None = None
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.exit_code: int | None = None
        self.done = False

    def status(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "command": self.command,
            "running": not self.done,
            "exit_code": self.exit_code,
            "stdout": bytes(self.stdout).decode("utf-8", errors="replace"),
            "stderr": bytes(self.stderr).decode("utf-8", errors="replace"),
        }


class ShellTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()
        self._jobs: dict[str, BackgroundJob] = {}

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
            # Prefer PowerShell when available for richer command support, then
            # fall back to cmd.exe.
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            if pwsh:
                return pwsh, ["-NoProfile", "-NonInteractive", "-Command", command]
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
            if proc is not None:
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
            return json.dumps({"command": command, "error": str(e)})

    def bgjobs_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Manage background shell jobs. action=start launches a command, "
                "list shows all jobs, status/output reads one, kill terminates it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "list", "status", "kill"],
                    },
                    "command": {"type": "string", "description": "Command (for action=start)"},
                    "job_id": {"type": "string", "description": "Job id (status/kill)"},
                },
                "required": ["action"],
            },
        }

    def _get_job_or_error(self, job_id: str | None) -> BackgroundJob | str:
        """Look up a job by id; return the job or an error JSON string."""
        job = self._jobs.get(job_id or "")
        if not job:
            return json.dumps({"error": f"job not found: {job_id}"})
        return job

    async def bgjobs(
        self,
        action: str,
        command: str | None = None,
        job_id: str | None = None,
    ) -> str:
        if action == "start":
            if not command:
                return json.dumps({"error": "command required for action=start"})
            return await self._start_job(command)
        if action == "list":
            return json.dumps({"jobs": [job.status() for job in self._jobs.values()]})
        if action in ("status", "output"):
            result = self._get_job_or_error(job_id)
            if isinstance(result, str):
                return result
            return json.dumps(result.status())
        if action == "kill":
            result = self._get_job_or_error(job_id)
            if isinstance(result, str):
                return result
            if result.proc and not result.done:
                result.proc.kill()
            return json.dumps({"job_id": result.job_id, "killed": True})
        return json.dumps({"error": f"unknown action: {action}"})

    async def _start_job(self, command: str) -> str:
        executable, args = self._shell_command(command)
        job_id = uuid.uuid4().hex[:8]
        job = BackgroundJob(job_id, command)
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                *args,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc), "command": command})
        job.proc = proc
        self._jobs[job_id] = job
        asyncio.create_task(self._drain(job))
        return json.dumps({"job_id": job_id, "command": command, "running": True})

    async def _drain(self, job: BackgroundJob) -> None:
        assert job.proc is not None
        stdout, stderr = await job.proc.communicate()
        job.stdout.extend(stdout)
        job.stderr.extend(stderr)
        job.exit_code = job.proc.returncode
        job.done = True
        # Clean up completed job after 5 minutes to prevent memory leak
        asyncio.get_running_loop().call_later(300, self._jobs.pop, job.job_id, None)

    def bash_output_schema(self) -> dict[str, Any]:
        return {
            "description": "Read new output from a background job.",
            "parameters": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        }

    async def bash_output(self, job_id: str) -> str:
        result = self._get_job_or_error(job_id)
        if isinstance(result, str):
            return result
        return json.dumps(result.status())

    def kill_shell_schema(self) -> dict[str, Any]:
        return {
            "description": "Terminate a background job.",
            "parameters": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        }

    async def kill_shell(self, job_id: str) -> str:
        return await self.bgjobs("kill", job_id=job_id)

    def wait_job_schema(self) -> dict[str, Any]:
        return {
            "description": "Wait for a background job to finish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "timeout": {"type": "integer", "default": 120},
                },
                "required": ["job_id"],
            },
        }

    async def wait_job(self, job_id: str, timeout: int = 120) -> str:
        result = self._get_job_or_error(job_id)
        if isinstance(result, str):
            return result
        job = result
        if job.done:
            return json.dumps(job.status())
        deadline = asyncio.get_running_loop().time() + float(timeout)
        while not job.done:
            if asyncio.get_running_loop().time() > deadline:
                return json.dumps({"error": "timeout waiting for job", **job.status()})
            await asyncio.sleep(0.2)
        return json.dumps(job.status())
