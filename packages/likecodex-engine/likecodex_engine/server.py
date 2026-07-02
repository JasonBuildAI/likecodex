"""HTTP bridge server exposing the Python agent engine.

This module has been refactored to delegate route handling to
the likecodex_engine.routes package. Each domain (agent, skills,
IDE, git, LSP, DeepSeek, static) has its own route module.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from aiohttp import web

from likecodex_engine.config_loader import engine_config_from_env
from likecodex_engine.routes import register_all_routes
from likecodex_engine.routes._shared import (
    APP_CONFIG,
    _BACKGROUND_TASKS,
    _RESOLVED_CONFIG_CACHE,
    _resolve_config,
    _ACTIVE_LOOPS,
    _ACTIVE_COORDINATORS,
    _CONTEXT_CACHE,
    _SESSION_STORE,
)
from likecodex_engine.routes.static import warmup_deepseek_cache

logger = logging.getLogger(__name__)


# ── Error handling middleware ──────────────────────────────────────


@web.middleware
async def _error_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    """Global error handling middleware.
    Catches all unhandled exceptions and returns structured JSON errors.
    Prevents 500 errors from leaking internal details.
    """
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error in %s %s", request.method, request.path)
        return web.json_response({"error": str(exc)}, status=500)


# ── Shutdown lifecycle ─────────────────────────────────────────────


async def _on_cleanup(app: web.Application) -> None:
    """Graceful shutdown: clean up all global state."""
    logger.info("Shutting down LikeCodex engine server...")

    for task in list(_BACKGROUND_TASKS):
        if not task.done():
            task.cancel()
    if _BACKGROUND_TASKS:
        await asyncio.gather(*_BACKGROUND_TASKS, return_exceptions=True)
    _BACKGROUND_TASKS.clear()

    for sid, loop in list(_ACTIVE_LOOPS.items()):
        if hasattr(loop, 'cancel'):
            try:
                loop.cancel()
            except Exception:
                pass
    _ACTIVE_LOOPS.clear()
    _ACTIVE_COORDINATORS.clear()
    _CONTEXT_CACHE.clear()

    if _SESSION_STORE is not None:
        try:
            _SESSION_STORE.close()
        except Exception:
            pass

    _RESOLVED_CONFIG_CACHE.clear()

    # Clear all lazy-init services from route modules
    from likecodex_engine.routes.ide import _reset_services as _reset_ide_services
    from likecodex_engine.routes.git import _reset_services as _reset_git_services
    from likecodex_engine.routes.lsp import _reset_services as _reset_lsp_services
    _reset_ide_services()
    _reset_git_services()
    _reset_lsp_services()

    logger.info("LikeCodex engine server shutdown complete")


def create_app(config: dict | None = None) -> web.Application:
    """Create and configure the aiohttp web application.

    All route handlers are registered via the routes package.
    """
    app = web.Application(middlewares=[_error_middleware])
    app[APP_CONFIG] = config or {}

    # Register all routes from the routes package
    register_all_routes(app, config or {})

    # Background cache warmup on startup
    async def _startup_warmup(app: web.Application) -> None:
        cfg = _resolve_config(app[APP_CONFIG])
        if cfg.get("provider", "deepseek") == "deepseek":
            asyncio.create_task(warmup_deepseek_cache())

    app.on_startup.append(_startup_warmup)
    app.on_cleanup.append(_on_cleanup)

    return app


def main() -> None:
    """Entry point for running the server directly."""
    host = os.environ.get("LIKECODEX_ENGINE_HOST", "127.0.0.1")
    port = int(os.environ.get("LIKECODEX_ENGINE_PORT", "9090"))
    config = engine_config_from_env()
    app = create_app(config)
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    main()
