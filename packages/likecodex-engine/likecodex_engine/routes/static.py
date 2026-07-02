"""Static file serving route handlers.

Handles: serving Web UI static files, SPA fallback, and lite version.
The static files are embedded in the package at `likecodex_engine/static/`.

To use: `cli.py --web` starts the engine which serves these files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from likecodex_engine.routes._shared import APP_CONFIG

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"
LITE_HTML = STATIC_DIR / "lite" / "index.html"


def get_static_dir() -> Path:
    """Return the path to the static files directory."""
    return STATIC_DIR


def has_static_files() -> bool:
    """Check if static files are available."""
    return STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists()


async def spa_handler(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def lite_handler(request: web.Request) -> web.FileResponse:
    return web.FileResponse(LITE_HTML)


async def warmup_deepseek_cache() -> None:
    try:
        from likecodex_engine.llm.deepseek import DeepSeekProvider
        from likecodex_engine.llm.base import Message, Role
        import os
        import logging
        logger = logging.getLogger(__name__)
        system_prompt = DeepSeekProvider.load_system_prompt()
        if not system_prompt:
            return
        provider = DeepSeekProvider(
            model="deepseek-v4-flash",
            api_key=os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LIKECODEX_LLM_API_KEY"),
        )
        warmup_msgs = [Message(role=Role.SYSTEM, content=system_prompt), Message(role=Role.USER, content=".")]
        await provider.complete(warmup_msgs, max_tokens=5)
        logger.debug("DeepSeek prefix cache warmup completed")
    except Exception as exc:
        logger.debug("DeepSeek prefix cache warmup skipped: %s", exc)


def register_routes(app: web.Application, config: dict) -> None:
    if not STATIC_DIR.exists():
        logger.info("Static directory not found: %s", STATIC_DIR)
        return

    app.router.add_static("/static/", path=str(STATIC_DIR), name="static")
    app.router.add_get("/", spa_handler)

    if LITE_HTML.exists():
        app.router.add_get("/lite", lite_handler)
