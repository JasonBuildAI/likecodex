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
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.pid: int = 0
        self._notify_callback: Any = None

    def on_complete(self, callback: Any) -> None:
        """Register a notification callback invoked when the job finishes."""
        self._notify_callback = callback

    def status(self) -> dict[str, Any]:
        elapsed = 0.0
        if self.start_time > 0:
            if self.done:
                elapsed = self.end_time - self.start_time
            else:
                elapsed = asyncio.get_running_loop().time() - self.start_time
        return {
            "job_id": self.job_id,
            "command": self.command,
            "running": not self.done,
            "exit_code": self.exit_code,
            "pid": self.pid,
            "elapsed_seconds": round(elapsed, 1),
            "stdout": bytes(self.stdout).decode("utf-8", errors="replace"),
            "stderr": bytes(self.stderr).decode("utf-8", errors="replace"),
        }


class ShellTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()
        self._jobs: dict[str, BackgroundJob] = {}
        self._history: list[dict[str, Any]] = []
        self._favorites: list[dict[str, Any]] = []
        self._history_file: Path = Path.home() / ".likecodex" / "shell_history.json"
        self._favorites_file: Path = Path.home() / ".likecodex" / "shell_favorites.json"
        self._load_history()
        self._load_favorites()

    # ── History Persistence ────────────────────────────────────

    def _load_history(self) -> None:
        """Load command history from persistent storage."""
        try:
            if self._history_file.exists():
                raw = self._history_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, list):
                    self._history = data[-500:]  # Keep last 500
        except Exception:
            self._history = []

    def _save_history(self) -> None:
        """Save command history to persistent storage."""
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            self._history_file.write_text(
                json.dumps(self._history[-500:], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _add_to_history(self, command: str, exit_code: int, cwd: str) -> None:
        """Add a command to history."""
        entry: dict[str, Any] = {
            "command": command,
            "exit_code": exit_code,
            "cwd": cwd or str(self.working_dir),
            "timestamp": asyncio.get_running_loop().time(),
            "favorite": False,
        }
        # Remove duplicate most recent occurrence
        self._history = [h for h in self._history if h.get("command") != command]
        self._history.append(entry)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        self._save_history()

    def _load_favorites(self) -> None:
        """Load favorite commands from persistent storage."""
        try:
            if self._favorites_file.exists():
                raw = self._favorites_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, list):
                    self._favorites = data
        except Exception:
            self._favorites = []

    def _save_favorites(self) -> None:
        """Save favorite commands to persistent storage."""
        try:
            self._favorites_file.parent.mkdir(parents=True, exist_ok=True)
            self._favorites_file.write_text(
                json.dumps(self._favorites, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

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
        cwd_str = str(self.working_dir)
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                *args,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=float(timeout))
            exit_code = proc.returncode
            # Record to history
            if proc.returncode is not None:
                self._add_to_history(command, proc.returncode, cwd_str)
            return json.dumps(
                {
                    "command": command,
                    "exit_code": exit_code,
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
            self._add_to_history(command, -1, cwd_str)
            return json.dumps({"command": command, "error": str(e)})

    def bgjobs_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Manage background shell jobs. action=start launches a command, "
                "list shows all jobs, status/output reads one, kill/stop terminates it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "list", "status", "kill", "stop", "output"],
                    },
                    "command": {"type": "string", "description": "Command (for action=start)"},
                    "job_id": {"type": "string", "description": "Job id (status/kill/stop/output)"},
                    "notify": {"type": "boolean", "description": "Send notification when job completes (for action=start)"},
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
        notify: bool = False,
    ) -> str:
        if action == "start":
            if not command:
                return json.dumps({"error": "command required for action=start"})
            return await self._start_job(command, notify=notify)
        if action == "list":
            return json.dumps({
                "jobs": [job.status() for job in self._jobs.values()],
                "total": len(self._jobs),
                "running": sum(1 for job in self._jobs.values() if not job.done),
            })
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
        if action == "stop":
            result = self._get_job_or_error(job_id)
            if isinstance(result, str):
                return result
            if result.proc and not result.done:
                result.proc.terminate()
            return json.dumps({"job_id": result.job_id, "stopped": True})
        return json.dumps({"error": f"unknown action: {action}"})

    async def _start_job(self, command: str, notify: bool = False) -> str:
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
        job.start_time = asyncio.get_running_loop().time()
        if proc.pid:
            job.pid = proc.pid
        if notify:
            job.on_complete(lambda jid=job_id: self._notify_completed(jid))
        self._jobs[job_id] = job
        asyncio.create_task(self._drain(job))
        return json.dumps({"job_id": job_id, "command": command, "running": True, "pid": job.pid})

    async def _drain(self, job: BackgroundJob) -> None:
        assert job.proc is not None
        stdout, stderr = await job.proc.communicate()
        job.stdout.extend(stdout)
        job.stderr.extend(stderr)
        job.exit_code = job.proc.returncode
        job.end_time = asyncio.get_running_loop().time()
        job.done = True
        # Invoke completion notification callback if registered
        if job._notify_callback:
            try:
                job._notify_callback()
            except Exception:
                pass
        # Clean up completed job after 5 minutes to prevent memory leak
        asyncio.get_running_loop().call_later(300, self._jobs.pop, job.job_id, None)

    def _notify_completed(self, job_id: str) -> None:
        """Notification callback when a background job completes.

        Logs completion and stores notification in job metadata.
        """
        job = self._jobs.get(job_id)
        if job:
            logger = logging.getLogger(__name__)
            logger.info(
                "Job %s completed: %s (exit_code=%s, elapsed=%.1fs)",
                job_id, job.command, job.exit_code, job.end_time - job.start_time,
            )

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

    # ── Phase 6.14: Command History & Favorites ────────────────

    def history_schema(self) -> dict[str, Any]:
        return {
            "description": "Browse, search, and re-execute command history. "
            "Actions: list (with optional search), get (by index), re-run (by index).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get", "clear"],
                        "description": "Action to perform",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query to filter history (for action=list)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20)",
                    },
                },
                "required": ["action"],
            },
        }

    async def history(self, action: str = "list", query: str = "", limit: int = 20) -> str:
        """Browse and manage command history."""
        if action == "clear":
            self._history = []
            self._save_history()
            return json.dumps({"ok": True, "message": "History cleared"})

        if action == "get":
            return json.dumps({
                "total": len(self._history),
                "history": [
                    {
                        "index": i,
                        **{k: v for k, v in entry.items() if k != "favorite"},
                    }
                    for i, entry in enumerate(self._history)
                ],
            })

        # Default: list with optional search
        results = list(reversed(self._history))
        if query:
            q = query.lower()
            results = [h for h in results if q in h.get("command", "").lower()]

        limited = results[:limit]
        return json.dumps({
            "total": len(self._history),
            "filtered": len(results),
            "history": [
                {
                    "index": len(self._history) - 1 - i,
                    "command": entry["command"],
                    "exit_code": entry.get("exit_code"),
                    "cwd": entry.get("cwd", ""),
                    "timestamp": entry.get("timestamp", 0),
                }
                for i, entry in enumerate(limited)
            ],
        }, ensure_ascii=False)

    def favorites_schema(self) -> dict[str, Any]:
        return {
            "description": "Manage favorite commands for quick re-execution. "
            "Actions: list, add, remove, re-run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "add", "remove"],
                        "description": "Action to perform",
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to add/remove (required for add/remove)",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label for the favorite",
                    },
                },
                "required": ["action"],
            },
        }

    async def favorites(self, action: str = "list", command: str = "", label: str = "") -> str:
        """Manage favorite commands."""
        if action == "add":
            if not command:
                return json.dumps({"error": "command required for add"})
            # Remove duplicate
            self._favorites = [f for f in self._favorites if f.get("command") != command]
            self._favorites.append({
                "command": command,
                "label": label or command[:40],
                "timestamp": asyncio.get_running_loop().time(),
            })
            self._save_favorites()
            return json.dumps({"ok": True, "command": command, "label": label or command[:40]})

        if action == "remove":
            if not command:
                return json.dumps({"error": "command required for remove"})
            self._favorites = [f for f in self._favorites if f.get("command") != command]
            self._save_favorites()
            return json.dumps({"ok": True, "removed": command})

        # Default: list
        return json.dumps({
            "favorites": [
                {
                    "index": i,
                    **entry,
                }
                for i, entry in enumerate(self._favorites)
            ],
            "total": len(self._favorites),
        }, ensure_ascii=False)

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

    # ── Phase 6.11: AI Command Enhancement ──────────────────────

    SENSITIVE_PATTERNS: list[tuple[str, str]] = [
        (r"rm\s+-rf\s+(/|\\\\)(\s|$)", "rm -rf / or root is dangerous"),
        (r":\(\s*\^\s*D\s*\)|\\x00|\\xff", "Binary data injection detected"),
        (r"mkfs\.|dd if=.*of=/dev/sd", "Dangerous disk operation"),
        (r"chmod\s+777\s+/", "Overly permissive root permission"),
        (r"wget.*\|\s*(ba|z)?sh", "Piping unverified download to shell"),
        (r"curl.*\|\s*(ba|z)?sh", "Piping unverified download to shell"),
        (r">\s*/dev/(sda|sdb|nvme|mmc)", "Direct disk write"),
        (r"shutdown|reboot|halt|poweroff", "System shutdown/reboot"),
        (r"fork\s*\(\s*\)|:(){:|bomb", "Fork bomb / DoS pattern"),
    ]

    DANGEROUS_COMMANDS: list[str] = [
        "rm -rf /", "mkfs", "dd if=", ":(){:",
        "chmod 777 /", "chown -R",
    ]

    def _detect_project_type(self) -> dict[str, Any]:
        """Detect project type, language, and build system from working directory."""
        info: dict[str, Any] = {
            "has_setup_py": False,
            "has_pyproject_toml": False,
            "has_package_json": False,
            "has_cargo_toml": False,
            "has_gradle": False,
            "has_makefile": False,
            "has_dockerfile": False,
            "has_git": False,
            "python_version": "",
            "node_version": "",
            "project_type": "unknown",
            "os": sys.platform,
        }

        try:
            wd = self.working_dir
            info["has_setup_py"] = (wd / "setup.py").exists()
            info["has_pyproject_toml"] = (wd / "pyproject.toml").exists()
            info["has_package_json"] = (wd / "package.json").exists()
            info["has_cargo_toml"] = (wd / "Cargo.toml").exists()
            info["has_gradle"] = (wd / "build.gradle").exists() or (wd / "build.gradle.kts").exists()
            info["has_makefile"] = (wd / "Makefile").exists()
            info["has_dockerfile"] = (wd / "Dockerfile").exists()
            info["has_git"] = (wd / ".git").exists()

            if info["has_cargo_toml"]:
                info["project_type"] = "rust"
            elif info["has_pyproject_toml"] or info["has_setup_py"]:
                info["project_type"] = "python"
            elif info["has_package_json"]:
                info["project_type"] = "node"
            elif info["has_gradle"]:
                info["project_type"] = "java"
            elif info["has_makefile"]:
                info["project_type"] = "c_cpp"
            else:
                info["project_type"] = "other"
        except Exception:
            pass

        return info

    @staticmethod
    def _check_command_safety(command: str) -> list[dict[str, Any]]:
        """Check a command against safety rules and return warnings."""
        import re
        warnings: list[dict[str, Any]] = []
        lowered = command.lower().strip()

        # Check against sensitive patterns
        for pattern, description in ShellTools.SENSITIVE_PATTERNS:
            if re.search(pattern, lowered):
                warnings.append({
                    "severity": "danger",
                    "message": description,
                    "pattern": pattern,
                })

        # Check for dangerous commands
        for dangerous in ShellTools.DANGEROUS_COMMANDS:
            if dangerous in lowered:
                warnings.append({
                    "severity": "danger",
                    "message": f"Command contains dangerous pattern: {dangerous}",
                })

        return warnings

    @staticmethod
    def _cleanup_command(command: str) -> str:
        """Clean up command: remove leading symbols, handle chains.

        Removes:
        - Leading $ or # or > symbols (common when pasting from docs)
        - Leading whitespace
        - Trailing semicolons
        - Handles command chains (; || &&)
        """
        cleaned = command.strip()

        # Remove leading shell prompt symbols
        while cleaned and cleaned[0] in ("$", "#", ">", "%"):
            cleaned = cleaned[1:].strip()
            if not cleaned:
                return ""

        # Remove leading whitespace again after symbol cleanup
        cleaned = cleaned.strip()

        # Remove trailing semicolons
        while cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip()

        return cleaned

    @staticmethod
    def _split_command_chain(command: str) -> list[dict[str, Any]]:
        """Split a command chain into individual commands.

        Handles: ; (semicolon), && (AND), || (OR), | (pipe)
        Returns list of {command, separator} dicts.
        """
        import re

        chain: list[dict[str, Any]] = []
        # Regex to split on ;, &&, ||, | while keeping track of the separator
        parts: list[tuple[str, str]] = re.findall(
            r'(?:\\.|[^;|&])+|(;|&&|\|\||\|)',
            command,
        )

        # Actually, let's do this more carefully
        current = ""
        i = 0
        while i < len(command):
            if command[i:i+2] == "&&":
                if current.strip():
                    chain.append({"command": current.strip(), "separator": "&&"})
                current = ""
                i += 2
            elif command[i:i+2] == "||":
                if current.strip():
                    chain.append({"command": current.strip(), "separator": "||"})
                current = ""
                i += 2
            elif command[i] == ";":
                if current.strip():
                    chain.append({"command": current.strip(), "separator": ";"})
                current = ""
                i += 1
            elif command[i] == "|" and (i == 0 or command[i-1] != "\\"):
                if current.strip():
                    chain.append({"command": current.strip(), "separator": "|"})
                current = ""
                i += 1
            else:
                current += command[i]
                i += 1

        if current.strip():
            chain.append({"command": current.strip(), "separator": ""})

        return chain if len(chain) > 1 else []

    def analyze_command_schema(self) -> dict[str, Any]:
        return {
            "description": "Analyze a command for safety issues, project context, and chain structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to analyze"},
                },
                "required": ["command"],
            },
        }

    async def analyze_command(self, command: str) -> str:
        """Analyze a command for safety, context, and structure."""
        cleaned = self._cleanup_command(command)
        chain = self._split_command_chain(cleaned) if "&&" in cleaned or "||" in cleaned or ";" in cleaned or "|" in cleaned else []
        safety = self._check_command_safety(cleaned)
        project = self._detect_project_type()

        result: dict[str, Any] = {
            "original": command,
            "cleaned": cleaned,
            "has_chain": len(chain) > 0,
            "chain": chain if chain else None,
            "safety_warnings": safety,
            "is_safe": len(safety) == 0,
            "project_context": project,
        }

        return json.dumps(result, ensure_ascii=False)

    def suggest_command_schema(self) -> dict[str, Any]:
        return {
            "description": "Get context-aware command suggestions based on project type and OS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "What the user wants to do (e.g., 'install dependencies', 'run tests', 'build')",
                    },
                    "project_type": {
                        "type": "string",
                        "description": "Override project type (python, node, rust, java, etc.)",
                    },
                },
                "required": ["intent"],
            },
        }

    async def suggest_command(self, intent: str, project_type: str = "") -> str:
        """Suggest context-aware commands for a given intent."""
        proj = self._detect_project_type() if not project_type else {"project_type": project_type, "os": sys.platform}
        ptype = proj.get("project_type", "unknown")
        os_name = proj.get("os", sys.platform)

        intent_lower = intent.lower()

        # Build suggestion map based on project type
        suggestions: dict[str, dict[str, list[str]]] = {
            "python": {
                "install": ["pip install -e .", "pip install -r requirements.txt", "pip install ."],
                "test": ["pytest", "pytest -v", "python -m pytest", "tox"],
                "build": ["python -m build", "pip install --upgrade build && python -m build"],
                "run": ["python main.py", "python -m likecodex_engine.server", "uvicorn main:app"],
                "lint": ["ruff check .", "flake8", "pylint src/"],
                "format": ["ruff format .", "black .", "isort ."],
                "clean": ["find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; find . -name '*.pyc' -delete"],
                "deps": ["pip list --format=columns", "pip freeze > requirements.txt", "pipdeptree"],
            },
            "node": {
                "install": ["npm install", "yarn", "pnpm install"],
                "test": ["npm test", "npm run test", "npx vitest run", "npx jest"],
                "build": ["npm run build", "npx next build"],
                "run": ["npm run dev", "npx next dev", "node server.js"],
                "lint": ["npx eslint .", "npm run lint"],
                "format": ["npx prettier --write .", "npm run format"],
                "clean": ["rm -rf node_modules .next dist"],
                "deps": ["npm ls --depth=0", "npx npm-check-updates"],
            },
            "rust": {
                "install": ["cargo build", "cargo build --release"],
                "test": ["cargo test", "cargo test -- --nocapture", "cargo nextest run"],
                "build": ["cargo build", "cargo build --release"],
                "run": ["cargo run", "cargo run --release"],
                "lint": ["cargo clippy -- -D warnings", "cargo fmt --check"],
                "format": ["cargo fmt"],
                "clean": ["cargo clean"],
                "deps": ["cargo tree", "cargo outdated"],
            },
            "java": {
                "install": ["./gradlew build", "mvn install", "gradle build"],
                "test": ["./gradlew test", "mvn test"],
                "build": ["./gradlew build", "mvn package"],
                "run": ["./gradlew run", "mvn exec:java"],
                "clean": ["./gradlew clean", "mvn clean"],
            },
        }

        # Generic commands for any project type
        generic: dict[str, list[str]] = {
            "status": ["git status", "git log --oneline -5"],
            "diff": ["git diff", "git diff --cached"],
            "log": ["git log --oneline --graph --all -20"],
            "branch": ["git branch -a", "git branch -vv"],
            "search": ["grep -r", "rg"],
        }

        # Find matching suggestions
        matches: list[str] = []
        all_cmds = suggestions.get(ptype, {})
        for key, cmds in {**all_cmds, **generic}.items():
            if key in intent_lower or intent_lower in key:
                matches.extend(cmd for cmd in cmds if cmd not in matches)

        # If no specific match, return top suggestions for project type
        if not matches:
            default_cmds = suggestions.get(ptype, {}).get("run", []) + ["git status", "ls -la", "pwd"]
            matches = default_cmds[:3]

        # Filter out commands that don't exist on windows
        if os_name == "win32":
            matches = [m for m in matches if not m.startswith("find . ")]

        return json.dumps({
            "intent": intent,
            "project_type": ptype,
            "suggestions": matches[:5],
            "os": os_name,
        }, ensure_ascii=False)
