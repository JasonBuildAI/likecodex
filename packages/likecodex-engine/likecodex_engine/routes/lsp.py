"""LSP API route handlers.

Handles: definition, references, hover, diagnostics via Language Server Protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

from likecodex_engine.routes._shared import _cfg_wd

logger = logging.getLogger(__name__)

_lsp_manager: Any = None


def _reset_services() -> None:
    """Reset all lazy-init services (called during shutdown)."""
    global _lsp_manager
    _lsp_manager = None


def _get_lsp_manager(working_dir: str):
    global _lsp_manager
    if _lsp_manager is None:
        from likecodex_engine.lsp.manager import LspManager
        _lsp_manager = LspManager(working_dir)
    return _lsp_manager


async def _lsp_handler(request: web.Request, method: str) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    file_path = data.get("file_path", "")
    symbol = data.get("symbol", "")
    if not file_path or not symbol:
        return web.json_response({"error": "file_path and symbol are required"}, status=400)
    manager = _get_lsp_manager(wd)
    func = getattr(manager, method)
    result = await func(file_path, data.get("line", 1), symbol)
    return web.json_response(json.loads(result) if isinstance(result, str) else {"result": result})


async def ide_lsp_definition(request: web.Request) -> web.Response:
    return await _lsp_handler(request, "definition")


async def ide_lsp_references(request: web.Request) -> web.Response:
    return await _lsp_handler(request, "references")


async def ide_lsp_hover(request: web.Request) -> web.Response:
    return await _lsp_handler(request, "hover")


async def ide_lsp_diagnostics(request: web.Request) -> web.Response:
    return web.json_response({"diagnostics": []})


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_post("/api/ide/lsp/definition", ide_lsp_definition)
    app.router.add_post("/api/ide/lsp/references", ide_lsp_references)
    app.router.add_post("/api/ide/lsp/hover", ide_lsp_hover)
    app.router.add_get("/api/ide/lsp/diagnostics", ide_lsp_diagnostics)
