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
