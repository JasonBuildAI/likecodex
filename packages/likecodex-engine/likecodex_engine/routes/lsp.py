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
    """Run diagnostics on a file or directory and return structured results."""
    _, wd = _cfg_wd(request)
    path = request.query.get("path", ".")
    from likecodex_engine.tools.lsp import LspTools
    tools = LspTools(wd)
    result_str = await tools.diagnostics(path)
    data = json.loads(result_str)
    # Parse output into structured diagnostics if raw output is present
    if data.get("output"):
        parsed = []
        for line in data["output"].split("\n"):
            line = line.strip()
            if not line:
                continue
            # Try to parse ruff/pyright style: file:line:col: severity message
            import re as _re
            m = _re.match(r"(.+?):(\d+):(\d+):\s*(\w+):\s*(.+)", line)
            if m:
                parsed.append({
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "column": int(m.group(3)),
                    "severity": m.group(4).lower(),
                    "message": m.group(5),
                    "source": data.get("checker", ""),
                })
            else:
                # Fallback: treat as full line diagnostic
                parsed.append({
                    "file": path,
                    "line": 0,
                    "column": 0,
                    "severity": "error" if data.get("exit_code", 0) != 0 else "warning",
                    "message": line,
                    "source": data.get("checker", ""),
                })
        data["diagnostics"] = parsed
        data.pop("output", None)
    return web.json_response(data)


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_post("/api/ide/lsp/definition", ide_lsp_definition)
    app.router.add_post("/api/ide/lsp/references", ide_lsp_references)
    app.router.add_post("/api/ide/lsp/hover", ide_lsp_hover)
    app.router.add_get("/api/ide/lsp/diagnostics", ide_lsp_diagnostics)
