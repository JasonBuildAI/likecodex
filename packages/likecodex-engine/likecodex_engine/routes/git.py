"""Git API route handlers.

Handles: git status, diff, stage, unstage, commit, log,
branches, checkout, create-branch, discard, search.
"""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from likecodex_engine.routes._shared import _cfg_wd

logger = logging.getLogger(__name__)

_git_service: Any = None


def _reset_services() -> None:
    """Reset all lazy-init services (called during shutdown)."""
    global _git_service
    _git_service = None


def _get_git_service(working_dir: str):
    global _git_service
    if _git_service is None:
        from likecodex_engine.git_service import GitService
        _git_service = GitService(working_dir)
    return _git_service


async def ide_git_status(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).get_status()
    return web.json_response(result)


async def ide_git_diff(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).get_diff(path=data.get("path", ""), staged=data.get("staged", False))
    return web.json_response(result)


async def ide_git_stage(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).stage_file(data.get("path", ""))
    return web.json_response(result)


async def ide_git_unstage(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).unstage_file(data.get("path", ""))
    return web.json_response(result)


async def ide_git_stage_all(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).stage_all()
    return web.json_response(result)


async def ide_git_commit(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).commit(message=data.get("message", ""), author=data.get("author", ""), email=data.get("email", ""))
    return web.json_response(result)


async def ide_git_log(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    count = int(request.query.get("count", "50"))
    result = await _get_git_service(wd).get_log(count=count)
    return web.json_response(result)


async def ide_git_branches(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).get_branches()
    return web.json_response(result)


async def ide_git_checkout(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).checkout_branch(data.get("name", ""))
    return web.json_response(result)


async def ide_git_create_branch(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).create_branch(data.get("name", ""))
    return web.json_response(result)


async def ide_git_discard(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).discard_changes(data.get("path", ""))
    return web.json_response(result)


async def ide_git_search(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    query = request.query.get("q", "")
    file_pattern = request.query.get("pattern", "")
    result = await _get_git_service(wd).search_files(query=query, file_pattern=file_pattern)
    return web.json_response(result)


async def ide_git_pull(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).git_pull()
    return web.json_response(result)


async def ide_git_push(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).git_push()
    return web.json_response(result)


async def ide_git_fetch(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).git_fetch()
    return web.json_response(result)


async def ide_git_stash(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    action = data.get("action", "list")
    message = data.get("message", "")
    if action == "push":
        result = await _get_git_service(wd).git_stash_push(message=message)
    elif action == "pop":
        result = await _get_git_service(wd).git_stash_pop()
    else:
        result = await _get_git_service(wd).git_stash_list()
    return web.json_response(result)


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_get("/api/ide/git/status", ide_git_status)
    app.router.add_post("/api/ide/git/diff", ide_git_diff)
    app.router.add_post("/api/ide/git/stage", ide_git_stage)
    app.router.add_post("/api/ide/git/unstage", ide_git_unstage)
    app.router.add_post("/api/ide/git/stage-all", ide_git_stage_all)
    app.router.add_post("/api/ide/git/commit", ide_git_commit)
    app.router.add_get("/api/ide/git/log", ide_git_log)
    app.router.add_get("/api/ide/git/branches", ide_git_branches)
    app.router.add_post("/api/ide/git/checkout", ide_git_checkout)
    app.router.add_post("/api/ide/git/create-branch", ide_git_create_branch)
    app.router.add_post("/api/ide/git/discard", ide_git_discard)
    app.router.add_get("/api/ide/git/search", ide_git_search)
    app.router.add_post("/api/ide/git/pull", ide_git_pull)
    app.router.add_post("/api/ide/git/push", ide_git_push)
    app.router.add_post("/api/ide/git/fetch", ide_git_fetch)
    app.router.add_post("/api/ide/git/stash", ide_git_stash)
