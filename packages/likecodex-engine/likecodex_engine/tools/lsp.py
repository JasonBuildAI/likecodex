"""Lightweight diagnostics bridge.

A full LSP client is overkill for the agent's needs; what the model actually
wants is "are there errors in this file/project?". This tool shells out to the
best available checker for a file's language (ruff/pyright, tsc, go vet, cargo
check, clippy) and returns structured pass/fail output. It degrades gracefully
when no checker is installed.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from likecodex_engine.tools.path_utils import resolve_in_working_dir

_EXT_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
}


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
            proc.kill()
            return json.dumps(
                {"path": path, "language": lang, "checked": False, "reason": "checker timed out", "diagnostics": []}
            )
        except Exception as exc:
            return json.dumps(
                {"path": path, "language": lang, "checked": False, "reason": str(exc), "diagnostics": []}
            )

        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        output = (out + err).strip()[:8000]
        return json.dumps(
            {
                "path": path,
                "language": lang,
                "checked": True,
                "checker": tool_name,
                "ok": code == 0,
                "exit_code": code,
                "output": output,
                "diagnostics": self._parse_diagnostics(output, code),
            }
        )

    @staticmethod
    def _language_for_dir(directory: Path) -> str | None:
        for ext, lang in _EXT_LANG.items():
            if any(directory.glob(f"*{ext}")) or any(directory.rglob(f"*{ext}")):
                return lang
        return None

    @staticmethod
    def _parse_diagnostics(output: str, exit_code: int) -> list[dict[str, Any]]:
        if exit_code == 0 or not output:
            return []
        return [{"message": line} for line in output.splitlines() if line.strip()][:50]

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
