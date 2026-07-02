"""LSP API route handlers.

Handles: definition, references, hover, diagnostics via Language Server Protocol.
Phase 7.7: SSE endpoint for real-time diagnostics push.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

from likecodex_engine.routes._shared import _cfg_wd, _make_sse_response, _sse_write, _sse_done

logger = logging.getLogger(__name__)

_lsp_manager: Any = None


def _reset_services() -> None:
    """Reset all lazy-init services (called during shutdown)."""
    global _lsp_manager
    _lsp_manager = None
    from likecodex_engine.tools.lsp import reset_monitor
    reset_monitor()


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
    from likecodex_engine.tools.lsp import get_monitor
    monitor = get_monitor(wd)
    data = await monitor.get_diagnostics(path)
    return web.json_response(data)


async def ide_lsp_diagnostics_sse(request: web.Request) -> web.Response:
    """SSE endpoint that pushes diagnostics updates when files change."""
    _, wd = _cfg_wd(request)
    from likecodex_engine.tools.lsp import get_monitor
    monitor = get_monitor(wd)

    response = _make_sse_response()
    await response.prepare(request)

    # Register this client for push notifications
    monitor.register_sse_client(response)

    try:
        # Send an initial keepalive
        await _sse_write(response, json.dumps({"type": "connected", "message": "Diagnostics SSE connected"}))

        # Keep connection alive until client disconnects
        while True:
            await asyncio.sleep(30)
            try:
                await _sse_write(response, json.dumps({"type": "keepalive"}))
            except (ConnectionError, ConnectionResetError, OSError):
                break
    except asyncio.CancelledError:
        pass
    finally:
        monitor.remove_sse_client(response)
        try:
            await _sse_done(response)
        except Exception:
            pass

    return response


async def ide_lsp_notify_change(request: web.Request) -> web.Response:
    """API endpoint to notify the server that a file changed (called from editor)."""
    _, wd = _cfg_wd(request)
    data = await request.json() if request.body_exists else {}
    file_path = data.get("file_path", "")
    if file_path:
        from likecodex_engine.tools.lsp import get_monitor
        monitor = get_monitor(wd)
        monitor.notify_file_changed(file_path)
    return web.json_response({"ok": True})


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_post("/api/ide/lsp/definition", ide_lsp_definition)
    app.router.add_post("/api/ide/lsp/references", ide_lsp_references)
    app.router.add_post("/api/ide/lsp/hover", ide_lsp_hover)
    app.router.add_get("/api/ide/lsp/diagnostics", ide_lsp_diagnostics)
    app.router.add_get("/api/ide/lsp/diagnostics/sse", ide_lsp_diagnostics_sse)
    app.router.add_post("/api/ide/lsp/notify-change", ide_lsp_notify_change)
