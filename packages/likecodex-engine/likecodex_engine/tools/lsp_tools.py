"""LSP tool wrappers."""

from __future__ import annotations

from typing import Any

from likecodex_engine.lsp.manager import LspManager
from likecodex_engine.tools.lsp import LspTools as CheckerTools


_SYMBOL_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "line": {"type": "integer"},
        "symbol": {"type": "string"},
    },
    "required": ["file", "line", "symbol"],
}


class LspSemanticTools:
    def __init__(self, working_dir: str) -> None:
        self.working_dir = working_dir
        self.manager = LspManager(working_dir)
        self.checker = CheckerTools(working_dir)

    def lsp_definition_schema(self) -> dict[str, Any]:
        return {"description": "Jump to symbol definition via LSP.", "parameters": _SYMBOL_PARAMS}

    def lsp_references_schema(self) -> dict[str, Any]:
        return {"description": "Find symbol references via LSP (falls back to grep hint).", "parameters": _SYMBOL_PARAMS}

    def lsp_hover_schema(self) -> dict[str, Any]:
        return {"description": "Show hover docs for a symbol.", "parameters": _SYMBOL_PARAMS}

    def lsp_diagnostics_schema(self) -> dict[str, Any]:
        return self.checker.diagnostics_schema()

    async def lsp_definition(self, file: str, line: int, symbol: str) -> str:
        return await self.manager.definition(file, line, symbol)

    async def lsp_references(self, file: str, line: int, symbol: str) -> str:
        return await self.manager.references(file, line, symbol)

    async def lsp_hover(self, file: str, line: int, symbol: str) -> str:
        return await self.manager.hover(file, line, symbol)

    async def lsp_diagnostics(self, path: str = ".") -> str:
        return await self.checker.diagnostics(path)
