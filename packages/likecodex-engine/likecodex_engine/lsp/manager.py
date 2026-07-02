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

    # ── Remote LSP Support ───────────────────────────────────────────

    def register_remote_server_schema(self) -> dict[str, Any]:
        return {
            "description": "Register a remote LSP server (TCP/WebSocket)."
            " Connect to an LSP server running on a remote host.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Language ID (e.g. 'python', 'typescript')"},
                    "host": {"type": "string", "description": "Remote host (e.g. '192.168.1.100')"},
                    "port": {"type": "integer", "description": "TCP port (e.g. 2087 for pyright)"},
                },
                "required": ["language", "host", "port"],
            },
        }

    async def register_remote_server(self, language: str, host: str, port: int) -> str:
        """Connect to a remote LSP server via TCP."""
        if language in self._clients and language in getattr(self, "_remote_languages", set()):
            # Already connected remotely
            return json.dumps({"status": "already_connected", "language": language, "host": host, "port": port})

        try:
            reader, writer = await asyncio.open_connection(host, port)

            # Wrap the TCP connection in a minimal subprocess-like interface for LspClient
            proc = _TcpProcess(reader, writer)
            client = LspClient(proc)

            # Initialize LSP session
            await client.request(
                "initialize",
                {
                    "processId": None,
                    "rootUri": self.root.as_uri(),
                    "capabilities": {},
                },
            )
            await client.request("initialized", {})

            self._clients[language] = client
            if not hasattr(self, "_remote_languages"):
                self._remote_languages = set()
            self._remote_languages.add(language)

            return json.dumps({
                "status": "connected",
                "language": language,
                "host": host,
                "port": port,
            })
        except (OSError, TimeoutError, ConnectionRefusedError) as e:
            return json.dumps({"error": f"Failed to connect to remote LSP at {host}:{port}: {e}"})

    def list_remote_servers_schema(self) -> dict[str, Any]:
        return {
            "description": "List all registered remote LSP server connections.",
            "parameters": {"type": "object", "properties": {}},
        }

    async def list_remote_servers(self) -> str:
        """List active remote LSP connections."""
        remote = getattr(self, "_remote_languages", set())
        servers = []
        for lang in remote:
            client = self._clients.get(lang)
            servers.append({
                "language": lang,
                "connected": client is not None,
            })
        return json.dumps({"remote_servers": servers, "count": len(servers)})

    def disconnect_remote_schema(self) -> dict[str, Any]:
        return {
            "description": "Disconnect a remote LSP server by language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Language to disconnect"},
                },
                "required": ["language"],
            },
        }

    async def disconnect_remote(self, language: str) -> str:
        """Disconnect a remote LSP server."""
        client = self._clients.pop(language, None)
        remote = getattr(self, "_remote_languages", set())
        remote.discard(language)
        if client:
            await client.close()
            return json.dumps({"status": "disconnected", "language": language})
        return json.dumps({"error": f"No remote connection for {language}"})


class _TcpProcess:
    """Minimal subprocess-like wrapper around a TCP connection for LspClient compat."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.stdin = _TcpStdin(writer)
        self.stdout = _TcpStdout(reader)
        self.returncode = None

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass

    async def wait(self) -> int:
        return 0


class _TcpStdin:
    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self._writer = writer

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    async def drain(self) -> None:
        await self._writer.drain()


class _TcpStdout:
    def __init__(self, reader: asyncio.StreamReader) -> None:
        self._reader = reader
        self._buffer = b""

    async def readline(self) -> bytes:
        line = await self._reader.readline()
        return line

    async def readexactly(self, n: int) -> bytes:
        return await self._reader.readexactly(n)
