"""Route handlers for the LikeCodex engine HTTP server.

Each module handles a specific domain of the API.
"""

from __future__ import annotations

from typing import Any

from aiohttp import web

from likecodex_engine.routes import agent, deepseek, git, ide, lsp, mcp, share, skills, static


def register_all_routes(app: web.Application, config: dict[str, Any]) -> None:
    """Register all route handlers onto the application."""
    agent.register_routes(app, config)
    skills.register_routes(app, config)
    ide.register_routes(app, config)
    git.register_routes(app, config)
    lsp.register_routes(app, config)
    deepseek.register_routes(app, config)
    mcp.register_routes(app, config)
    share.register_routes(app, config)
    static.register_routes(app, config)
