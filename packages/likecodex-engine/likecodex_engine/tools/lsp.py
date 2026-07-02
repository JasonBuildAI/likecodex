"""Lightweight diagnostics bridge.

A full LSP client is overkill for the agent's needs; what the model actually
wants is "are there errors in this file/project?". This tool shells out to the
best available checker for a file's language (ruff/pyright, tsc, go vet, cargo
check, clippy) and returns structured pass/fail output. It degrades gracefully
when no checker is installed.

Phase 7.7: LSP Real-time Updates
- DiagnosticsMonitor watches files for changes and debounces re-diagnostics
- SSE endpoint pushes diagnostics updates to the frontend
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from aiohttp import web
from likecodex_engine.tools.path_utils import resolve_in_working_dir

logger = logging.getLogger(__name__)

_EXT_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
}

# ── Diagnostics Monitor ──────────────────────────────────────────────────


class DiagnosticsMonitor:
    """Watches files for changes and debounces re-diagnostics.

    Maintains a cache of last diagnostics results per path. When a file
    changes, it schedules a re-check after a debounce period. Results can
    be pushed to SSE subscribers.
    """

    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()
        self._cache: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, asyncio.Task[None]] = {}
        self._debounce_secs: float = 1.0
        self._sse_clients: list[web.StreamResponse] = []

    async def get_diagnostics(
        self, path: str = ".", force: bool = False
    ) -> dict[str, Any]:
        """Get (or run) diagnostics for a path. Returns cached result if fresh."""
        now = time.time()
        cached = self._cache.get(path)
        if cached and not force and (now - cached.get("_ts", 0)) < 30.0:
            return cached

        tools = LspTools(str(self.working_dir))
        result_str = await tools.diagnostics(path)
        data = json.loads(result_str)
        # Parse structured diagnostics
        data["_ts"] = now
        self._cache[path] = data
        return data

    async def schedule_diagnostics(self, path: str) -> None:
        """Schedule a debounced re-diagnostics for the given path."""
        if path in self._pending:
            self._pending[path].cancel()
        self._pending[path] = asyncio.create_task(self._debounced_check(path))

    async def _debounced_check(self, path: str) -> None:
        """Wait for debounce period, then run diagnostics and notify clients."""
        try:
            await asyncio.sleep(self._debounce_secs)
            data = await self.get_diagnostics(path, force=True)
            await self._notify_clients({
                "type": "diagnostics_update",
                "path": path,
                "diagnostics": data.get("diagnostics", []),
                "checked": data.get("checked", False),
                "language": data.get("language", ""),
                "ok": data.get("ok", False),
            })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Debounced diagnostics failed for %s: %s", path, e)
        finally:
            self._pending.pop(path, None)

    def notify_file_changed(self, file_path: str) -> None:
        """Called when a file changes. Schedule re-diagnostics."""
        rel = os.path.relpath(file_path, self.working_dir)
        ext = Path(file_path).suffix.lower()
        if ext in _EXT_LANG:
            asyncio.ensure_future(self.schedule_diagnostics(rel))

    def register_sse_client(self, response: web.StreamResponse) -> None:
        """Register an SSE client for push notifications."""
        self._sse_clients.append(response)

    def remove_sse_client(self, response: web.StreamResponse) -> None:
        """Remove a disconnected SSE client."""
        if response in self._sse_clients:
            self._sse_clients.remove(response)

    async def _notify_clients(self, event: dict[str, Any]) -> None:
        """Push an event to all connected SSE clients."""
        payload = json.dumps(event)
        dead: list[web.StreamResponse] = []
        for client in self._sse_clients:
            try:
                from likecodex_engine.routes._shared import _sse_write

                await _sse_write(client, payload)
            except (ConnectionError, ConnectionResetError, OSError):
                dead.append(client)
        for d in dead:
            self._sse_clients.remove(d)


# Singleton
_monitor: DiagnosticsMonitor | None = None


def get_monitor(working_dir: str) -> DiagnosticsMonitor:
    global _monitor
    if _monitor is None:
        _monitor = DiagnosticsMonitor(working_dir)
    return _monitor


def reset_monitor() -> None:
    global _monitor
    _monitor = None


# ── LSP Tools ────────────────────────────────────────────────────────────


class LspTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = Path(working_dir).resolve()

    def diagnostics_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Run static diagnostics on a file using the best available checker "
                "(ruff/pyright, tsc, go vet, cargo clippy). Returns errors/warnings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to check"},
                },
                "required": ["path"],
            },
        }

    async def diagnostics(self, path: str) -> str:
        try:
            target = resolve_in_working_dir(self.working_dir, path)
        except PermissionError as exc:
            return json.dumps({"error": str(exc), "diagnostics": []})
        if not target.exists():
            return json.dumps({"error": f"File not found: {path}", "diagnostics": []})

        if target.is_dir():
            lang = self._language_for_dir(target)
            if not lang:
                return json.dumps(
                    {
                        "path": path,
                        "language": "unknown",
                        "checked": False,
                        "reason": "unsupported language",
                        "diagnostics": [],
                    }
                )
            cmd = self._checker_for_dir(lang, str(target))
        else:
            lang = _EXT_LANG.get(target.suffix.lower())
            if not lang:
                return json.dumps(
                    {
                        "path": path,
                        "language": "unknown",
                        "checked": False,
                        "reason": "unsupported language",
                        "diagnostics": [],
                    }
                )
            cmd = self._checker_for(lang, str(target))

        if cmd is None:
            return json.dumps(
                {
                    "path": path,
                    "language": lang,
                    "checked": False,
                    "reason": "no checker installed",
                    "diagnostics": [],
                }
            )

        tool_name, args = cmd
        try:
            proc = await asyncio.create_subprocess_exec(
                tool_name,
                *args,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
            code = proc.returncode
        except TimeoutError:
            if proc is not None:
                proc.kill()
            return json.dumps(
                {"path": path, "language": lang, "checked": False, "reason": "checker timed out", "diagnostics": []}
            )
        except Exception as exc:
            return json.dumps({"path": path, "language": lang, "checked": False, "reason": str(exc), "diagnostics": []})

        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        output = (out + err).strip()[:8000]
        parsed_diagnostics = self._parse_diagnostics(output, path, code, tool_name)
        return json.dumps(
            {
                "path": path,
                "language": lang,
                "checked": True,
                "checker": tool_name,
                "ok": code == 0,
                "exit_code": code,
                "diagnostics": parsed_diagnostics,
            }
        )

    @staticmethod
    def _language_for_dir(directory: Path) -> str | None:
        for ext, lang in _EXT_LANG.items():
            if any(directory.glob(f"*{ext}")) or any(directory.rglob(f"*{ext}")):
                return lang
        return None

    @staticmethod
    def _parse_diagnostics(output: str, path: str, exit_code: int, checker: str) -> list[dict[str, Any]]:
        """Parse checker output into structured diagnostics."""
        if exit_code == 0 or not output:
            return []
        parsed = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            # Try ruff/pyright style: file:line:col: severity message
            m = re.match(r"(.+?):(\d+):(\d+):\s*(\w+):\s*(.+)", line)
            if m:
                parsed.append({
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "column": int(m.group(3)),
                    "severity": m.group(4).lower(),
                    "message": m.group(5),
                    "source": checker,
                })
            elif ": error:" in line or ": warning:" in line:
                # Try file:line:col error/warning style
                m2 = re.match(r"(.+?):(\d+):(\d+):\s*(error|warning):\s*(.+)", line)
                if m2:
                    parsed.append({
                        "file": m2.group(1),
                        "line": int(m2.group(2)),
                        "column": int(m2.group(3)),
                        "severity": m2.group(4).lower(),
                        "message": m2.group(5),
                        "source": checker,
                    })
            else:
                parsed.append({
                    "file": path,
                    "line": 0,
                    "column": 0,
                    "severity": "error" if exit_code != 0 else "warning",
                    "message": line,
                    "source": checker,
                })
        return parsed[:50]

    @staticmethod
    def _checker_for_dir(lang: str, dir_path: str) -> tuple[str, list[str]] | None:
        if lang == "python":
            if shutil.which("ruff"):
                return "ruff", ["check", dir_path]
            py_files = sorted(Path(dir_path).glob("*.py"))
            if py_files and shutil.which("python"):
                return "python", ["-m", "py_compile", str(py_files[0])]
            return None
        if lang in ("typescript", "javascript"):
            if shutil.which("tsc"):
                return "tsc", ["--noEmit", dir_path]
            return None
        if lang == "go":
            if shutil.which("go"):
                return "go", ["vet", "./..."]
            return None
        if lang == "rust":
            if shutil.which("cargo"):
                return "cargo", ["clippy", "--quiet"]
            return None
        return None

    @staticmethod
    def _checker_for(lang: str, file_path: str) -> tuple[str, list[str]] | None:
        if lang == "python":
            if shutil.which("ruff"):
                return "ruff", ["check", file_path]
            if shutil.which("pyright"):
                return "pyright", [file_path]
            if shutil.which("python"):
                return "python", ["-m", "py_compile", file_path]
            return None
        if lang in ("typescript", "javascript"):
            if shutil.which("tsc"):
                return "tsc", ["--noEmit", file_path]
            if shutil.which("npx"):
                return "npx", ["--no-install", "tsc", "--noEmit", file_path]
            return None
        if lang == "go":
            if shutil.which("go"):
                return "go", ["vet", file_path]
            return None
        if lang == "rust":
            if shutil.which("cargo"):
                return "cargo", ["clippy", "--quiet"]
            return None
        return None
