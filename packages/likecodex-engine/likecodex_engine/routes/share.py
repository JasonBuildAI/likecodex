"""Session share HTTP API routes.

Endpoints
--------
POST   /session/share              — create a share link
GET    /session/share/{token}      — resolve / peek a share link
POST   /session/share/{token}/import — import a shared session
DELETE /session/share/{token}      — revoke a share link
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

from likecodex_engine.errors import ValidationError
from likecodex_engine.persistence.share import SessionShareService
from likecodex_engine.routes._shared import (
    _session_store,
    APP_CONFIG,
)

logger = logging.getLogger(__name__)

# ── Lazy singleton ──────────────────────────────────────────────────────

_SHARE_SERVICE: SessionShareService | None = None


def _share_service() -> SessionShareService:
    global _SHARE_SERVICE
    if _SHARE_SERVICE is None:
        _SHARE_SERVICE = SessionShareService(".likecodex/sessions.db")
    return _SHARE_SERVICE


def _reset_services() -> None:
    global _SHARE_SERVICE
    if _SHARE_SERVICE is not None:
        _SHARE_SERVICE.close()
        _SHARE_SERVICE = None


# ── Request helpers ─────────────────────────────────────────────────────


async def _read_json(request: web.Request) -> dict[str, Any]:
    try:
        return await request.json() if request.can_read_body else {}
    except (json.JSONDecodeError, Exception):
        return {}


# ── Handlers ────────────────────────────────────────────────────────────


async def handle_create_share(request: web.Request) -> web.Response:
    """POST /session/share — create a share link for a session."""
    data = await _read_json(request)
    session_id = data.get("session_id", "")
    expiry_hours = int(data.get("expiry_hours", 24))
    password = data.get("password")

    if not session_id:
        return web.json_response({"error": "session_id is required"}, status=400)

    store = _session_store()
    metadata = store.get_session_metadata(session_id)
    if not metadata:
        return web.json_response({"error": "Session not found"}, status=404)

    try:
        svc = _share_service()
        token = svc.create_share_link(
            session_id=session_id,
            expiry_hours=expiry_hours,
            password=password,
        )
    except ValidationError as exc:
        return web.json_response({"error": exc.message, "details": exc.details}, status=422)

    return web.json_response({"token": token, "session_id": session_id})


async def handle_get_share(request: web.Request) -> web.Response:
    """GET /session/share/{token} — resolve / peek a share link.

    If the share is password-protected the caller must provide the
    password in the ``X-Share-Password`` header or as a query
    parameter ``?password=``.
    """
    token = request.match_info.get("token", "")
    password = (
        request.headers.get("X-Share-Password")
        or request.query.get("password")
    )

    svc = _share_service()
    try:
        result = svc.resolve_share_link(token, password=password)
    except ValidationError as exc:
        return web.json_response({"error": exc.message, "details": exc.details}, status=403)

    if result is None:
        return web.json_response({"error": "Share link not found or expired"}, status=404)

    store = _session_store()
    metadata = store.get_session_metadata(result["session_id"])
    stats = store.get_session_stats(result["session_id"])

    return web.json_response({
        "share": result,
        "session": {
            "metadata": metadata,
            "stats": stats,
        },
    })


async def handle_import_share(request: web.Request) -> web.Response:
    """POST /session/share/{token}/import — import a shared session.

    Creates a new forked session in the current user's store.
    """
    token = request.match_info.get("token", "")
    data = await _read_json(request)
    password = data.get("password")

    svc = _share_service()
    try:
        result = svc.resolve_share_link(token, password=password)
    except ValidationError as exc:
        return web.json_response({"error": exc.message, "details": exc.details}, status=403)

    if result is None:
        return web.json_response({"error": "Share link not found or expired"}, status=404)

    store = _session_store()
    new_session_id = store.fork_session(
        source_session_id=result["session_id"],
        fork_metadata={"imported_from_share": token},
    )

    return web.json_response({
        "session_id": new_session_id,
        "original_session_id": result["session_id"],
    })


async def handle_revoke_share(request: web.Request) -> web.Response:
    """DELETE /session/share/{token} — revoke a share link."""
    token = request.match_info.get("token", "")
    svc = _share_service()
    ok = svc.revoke_share_link(token)
    if not ok:
        return web.json_response({"error": "Share link not found or already revoked"}, status=404)
    return web.json_response({"status": "revoked", "token": token})


# ── Route registration ──────────────────────────────────────────────────


def register_routes(app: web.Application, config: dict[str, Any]) -> None:
    """Register share route handlers."""
    app.router.add_post("/session/share", handle_create_share)
    app.router.add_get("/session/share/{token}", handle_get_share)
    app.router.add_post("/session/share/{token}/import", handle_import_share)
    app.router.add_delete("/session/share/{token}", handle_revoke_share)
"""Session share HTTP API routes.

Endpoints
--------
POST   /session/share              — create a share link
GET    /session/share/{token}      — resolve / peek a share link
POST   /session/share/{token}/import — import a shared session
DELETE /session/share/{token}      — revoke a share link
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

from likecodex_engine.errors import ValidationError
from likecodex_engine.persistence.share import SessionShareService
from likecodex_engine.persistence.session import SessionStore
from likecodex_engine.routes._shared import (
    _session_store,
    APP_CONFIG,
)

logger = logging.getLogger(__name__)

# ── Lazy singleton ──────────────────────────────────────────────────────

_SHARE_SERVICE: SessionShareService | None = None


def _share_service() -> SessionShareService:
    global _SHARE_SERVICE
    if _SHARE_SERVICE is None:
        db_path = ".likecodex/sessions.db"
        _SHARE_SERVICE = SessionShareService(db_path)
    return _SHARE_SERVICE


def _reset_services() -> None:
    global _SHARE_SERVICE
    if _SHARE_SERVICE is not None:
        _SHARE_SERVICE.close()
        _SHARE_SERVICE = None


# ── Request helpers ─────────────────────────────────────────────────────


def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        return json.loads(await request.read()) if request.can_read_body else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def _read_json(request: web.Request) -> dict[str, Any]:
    try:
        return await request.json() if request.can_read_body else {}
    except (json.JSONDecodeError, Exception):
        return {}


# ── Handlers ────────────────────────────────────────────────────────────


async def handle_create_share(request: web.Request) -> web.Response:
    """POST /session/share — create a share link for a session."""
    data = await _read_json(request)
    session_id = data.get("session_id", "")
    expiry_hours = int(data.get("expiry_hours", 24))
    password = data.get("password")

    if not session_id:
        return web.json_response({"error": "session_id is required"}, status=400)

    # Verify the session exists
    store = _session_store()
    metadata = store.get_session_metadata(session_id)
    if not metadata:
        return web.json_response({"error": "Session not found"}, status=404)

    try:
        svc = _share_service()
        token = svc.create_share_link(
            session_id=session_id,
            expiry_hours=expiry_hours,
            password=password,
        )
    except ValidationError as exc:
        return web.json_response({"error": exc.message, "details": exc.details}, status=422)

    return web.json_response({"token": token, "session_id": session_id})


async def handle_get_share(request: web.Request) -> web.Response:
    """GET /session/share/{token} — resolve / peek a share link.

    If the share is password-protected the caller must provide the
    password in the ``X-Share-Password`` header or as a query
    parameter ``?password=``.
    """
    token = request.match_info.get("token", "")
    password = (
        request.headers.get("X-Share-Password")
        or request.query.get("password")
    )

    svc = _share_service()
    try:
        result = svc.resolve_share_link(token, password=password)
    except ValidationError as exc:
        return web.json_response({"error": exc.message, "details": exc.details}, status=403)

    if result is None:
        return web.json_response({"error": "Share link not found or expired"}, status=404)

    # Include a session summary (without full event history)
    store = _session_store()
    metadata = store.get_session_metadata(result["session_id"])
    stats = store.get_session_stats(result["session_id"])

    return web.json_response({
        "share": result,
        "session": {
            "metadata": metadata,
            "stats": stats,
        },
    })


async def handle_import_share(request: web.Request) -> web.Response:
    """POST /session/share/{token}/import — import a shared session.

    Creates a new forked session in the current user's store.
    """
    token = request.match_info.get("token", "")
    data = await _read_json(request)
    password = data.get("password")

    svc = _share_service()
    try:
        result = svc.resolve_share_link(token, password=password)
    except ValidationError as exc:
        return web.json_response({"error": exc.message, "details": exc.details}, status=403)

    if result is None:
        return web.json_response({"error": "Share link not found or expired"}, status=404)

    # Fork the shared session into the local store
    store = _session_store()
    new_session_id = store.fork_session(
        source_session_id=result["session_id"],
        fork_metadata={"imported_from_share": token},
    )

    return web.json_response({
        "session_id": new_session_id,
        "original_session_id": result["session_id"],
    })


async def handle_revoke_share(request: web.Request) -> web.Response:
    """DELETE /session/share/{token} — revoke a share link."""
    token = request.match_info.get("token", "")
    svc = _share_service()
    ok = svc.revoke_share_link(token)
    if not ok:
        return web.json_response({"error": "Share link not found or already revoked"}, status=404)
    return web.json_response({"status": "revoked", "token": token})


# ── Route registration ──────────────────────────────────────────────────


def register_routes(app: web.Application, config: dict[str, Any]) -> None:
    """Register share route handlers."""
    app.router.add_post("/session/share", handle_create_share)
    app.router.add_get("/session/share/{token}", handle_get_share)
    app.router.add_post("/session/share/{token}/import", handle_import_share)
    app.router.add_delete("/session/share/{token}", handle_revoke_share)
