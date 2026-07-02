"""LSP server manager per language."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from likecodex_engine.lsp.client import LspClient
from likecodex_engine.lsp.position import find_symbol_column
from likecodex_engine.tools.encoding import read_text_detect


class LspManager:
    def __init__(self, root: str) -> None:

        self.root = Path(root).resolve()

        self._clients: dict[str, LspClient] = {}

        self._opened: set[str] = set()

        # ── Diagnostic storage ──────────────────────────────────────
        self._diagnostics: dict[str, list[dict]] = {}

    async def _get_client(self, lang: str) -> LspClient | None:

        if lang in self._clients:
            return self._clients[lang]

        cmd = self._server_command(lang)

        if not cmd:
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.root,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            client = LspClient(proc)

            await client.request(
                "initialize",
                {
                    "processId": None,
                    "rootUri": self.root.as_uri(),
                    "capabilities": {},
                },
            )

            await client.request("initialized", {})

            self._clients[lang] = client

            return client

        except (TimeoutError, OSError):
            return None

    async def _ensure_open(self, client: LspClient, path: Path) -> str:

        uri = path.as_uri()

        if uri in self._opened:
            return uri

        text = read_text_detect(path).text

        await client.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": self.detect_language(path),
                    "version": 1,
                    "text": text,
                }
            },
        )

        self._opened.add(uri)

        return uri

    @staticmethod
    def _server_command(lang: str) -> list[str] | None:

        if lang == "python":
            pyright = shutil.which("pyright-langserver") or shutil.which("pyright")

            if pyright:
                return [pyright, "--stdio"]

        if lang in ("typescript", "javascript"):
            tss = shutil.which("typescript-language-server")

            if tss:
                return [tss, "--stdio"]

        if lang == "go":
            gopls = shutil.which("gopls")

            if gopls:
                return [gopls, "serve"]

        return None

    @staticmethod
    def detect_language(path: Path) -> str:

        ext = path.suffix.lower()

        return {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
        }.get(ext, "unknown")

    async def _position(self, file_path: str, line: int, symbol: str) -> tuple[Path, LspClient, dict[str, int]] | None:

        path = (self.root / file_path).resolve()

        client = await self._get_client(self.detect_language(path))

        if not client:
            return None

        await self._ensure_open(client, path)

        column = find_symbol_column(path, line, symbol)

        return path, client, {"line": max(0, line - 1), "character": column}

    async def definition(self, file_path: str, line: int, symbol: str) -> str:

        pos = await self._position(file_path, line, symbol)

        if not pos:
            return json.dumps({"error": "No LSP server available for this language"})

        path, client, position = pos

        result = await client.request(
            "textDocument/definition",
            {"textDocument": {"uri": path.as_uri()}, "position": position},
        )

        return json.dumps({"definitions": result or []})

    async def references(self, file_path: str, line: int, symbol: str) -> str:

        pos = await self._position(file_path, line, symbol)

        if not pos:
            return json.dumps({"error": "No LSP server available for this language"})

        path, client, position = pos

        result = await client.request(
            "textDocument/references",
            {
                "textDocument": {"uri": path.as_uri()},
                "position": position,
                "context": {"includeDeclaration": True},
            },
        )

        return json.dumps({"references": result or []})

    async def hover(self, file_path: str, line: int, symbol: str) -> str:

        pos = await self._position(file_path, line, symbol)

        if not pos:
            return json.dumps({"error": "No LSP server available for this language"})

        path, client, position = pos

        result = await client.request(
            "textDocument/hover",
            {"textDocument": {"uri": path.as_uri()}, "position": position},
        )

        return json.dumps({"hover": result or {}})

    async def close(self) -> None:

        for c in self._clients.values():
            await c.close()

        self._clients.clear()

        self._opened.clear()

    # ── Diagnostics ──────────────────────────────────────────────────

    def diagnostics_schema(self) -> dict[str, Any]:
        return {
            "description": "Retrieve LSP diagnostics (errors/warnings) for a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path"},
                },
                "required": ["file_path"],
            },
        }

    async def diagnostics(self, file_path: str) -> str:
        """Get diagnostics for a file from LSP server, or from cache if already fetched."""
        path = (self.root / file_path).resolve()
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        client = await self._get_client(self.detect_language(path))
        if not client:
            return json.dumps({"error": "No LSP server available for this language"})

        uri = await self._ensure_open(client, path)

        # Try pull-based diagnostics first (LSP 3.17+)
        try:
            result = await client.request(
                "textDocument/diagnostic",
                {
                    "textDocument": {"uri": uri},
                    "identifier": "likecodex-diag",
                },
            )
            if result and "items" in (result.get("kind") or {}):
                items = result["kind"]["items"]
            elif result and isinstance(result, dict):
                items = result.get("items", [])
            else:
                items = []
        except Exception:
            items = self._diagnostics.get(uri, [])

        formatted = [
            {
                "line": d.get("range", {}).get("start", {}).get("line", 0) + 1,
                "column": d.get("range", {}).get("start", {}).get("character", 0) + 1,
                "severity": {1: "error", 2: "warning", 3: "info", 4: "hint"}.get(d.get("severity"), "info"),
                "message": d.get("message", ""),
                "source": d.get("source", "lsp"),
                "code": d.get("code"),
            }
            for d in (items or [])
        ]

        return json.dumps({
            "file": file_path,
            "diagnostics": formatted,
            "count": len(formatted),
            "errors": sum(1 for d in formatted if d["severity"] == "error"),
            "warnings": sum(1 for d in formatted if d["severity"] == "warning"),
        })

    # ── Code Actions ─────────────────────────────────────────────────

    def code_action_schema(self) -> dict[str, Any]:
        return {
            "description": "Request code actions (quick-fixes, refactors, etc.) from LSP for a file at a given line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path"},
                    "line": {"type": "integer", "description": "1-based line number"},
                },
                "required": ["file_path", "line"],
            },
        }

    async def code_action(self, file_path: str, line: int) -> str:
        """Get available code actions (quick fixes, refactors) for a position in a file."""
        path = (self.root / file_path).resolve()
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        client = await self._get_client(self.detect_language(path))
        if not client:
            return json.dumps({"error": "No LSP server available for this language"})

        uri = await self._ensure_open(client, path)
        zero_line = max(0, line - 1)

        try:
            result = await client.request(
                "textDocument/codeAction",
                {
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": zero_line, "character": 0},
                        "end": {"line": zero_line, "character": 0},
                    },
                    "context": {
                        "diagnostics": [],
                        "only": None,
                    },
                },
            )
        except Exception as e:
            return json.dumps({"error": f"codeAction request failed: {e}"})

        actions = []
        for action in (result or []):
            if isinstance(action, dict):
                title = action.get("title", "")
                kind = action.get("kind", "")
                edit = action.get("edit")
                command = action.get("command")
                actions.append({
                    "title": title,
                    "kind": kind,
                    "has_edit": edit is not None,
                    "command": command.get("command") if command else None,
                })

        return json.dumps({
            "file": file_path,
            "line": line,
            "actions": actions,
            "count": len(actions),
        })
