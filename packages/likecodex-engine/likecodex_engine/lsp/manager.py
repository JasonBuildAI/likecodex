"""LSP server manager per language."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from likecodex_engine.lsp.client import LspClient
from likecodex_engine.lsp.position import find_symbol_column
from likecodex_engine.tools.encoding import read_text_detect


class LspManager:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self._clients: dict[str, LspClient] = {}
        self._opened: set[str] = set()

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
