"""IM Bot adapter for Feishu/Lark and WeChat — calls LikeCodex HTTP API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from aiohttp import web

from approval_bridge import respond_ask, respond_permission, subscribe_events

API_BASE = os.environ.get("LIKECODEX_API_BASE", "http://127.0.0.1:8080")
SESSION_MAP: dict[str, str] = {}
PENDING_CARDS: dict[str, dict[str, Any]] = {}
log = logging.getLogger("imbot")


async def _platform_send(thread_id: str, card: dict[str, Any]) -> None:
    """Log card payload; platform SDKs replace this in production."""
    PENDING_CARDS[thread_id] = card
    log.info("IM card for %s: %s", thread_id, json.dumps(card, ensure_ascii=False))


async def handle_feishu(request: web.Request) -> web.Response:
    data = await request.json()
    thread_id = str(data.get("event", {}).get("message", {}).get("chat_id", "default"))
    text = data.get("event", {}).get("message", {}).get("content", "")
    session_id = SESSION_MAP.setdefault(thread_id, thread_id)
    async with request.app["client"].post(
        f"{API_BASE}/tasks",
        json={"prompt": text, "session_id": session_id},
    ) as resp:
        body = await resp.json()
    return web.json_response({"ok": True, "task": body})


async def handle_wechat(request: web.Request) -> web.Response:
    data = await request.json()
    thread_id = str(data.get("FromUserName", "wechat-default"))
    text = str(data.get("Content", ""))
    session_id = SESSION_MAP.setdefault(thread_id, thread_id)
    async with request.app["client"].post(
        f"{API_BASE}/tasks",
        json={"prompt": text, "session_id": session_id},
    ) as resp:
        body = await resp.json()
    return web.json_response({"ok": True, "task": body})


async def handle_card_action(request: web.Request) -> web.Response:
    """Webhook for platform button clicks (permission/ask)."""
    data = await request.json()
    thread_id = str(data.get("thread_id", "default"))
    kind = str(data.get("kind", ""))
    request_id = str(data.get("request_id", ""))
    client = request.app["client"]

    if kind == "permission":
        await respond_permission(
            client,
            API_BASE,
            request_id,
            approved=bool(data.get("approved")),
            grant_scope=str(data.get("grant_scope", "once")),
        )
    elif kind == "ask":
        answers = data.get("answers") or []
        await respond_ask(client, API_BASE, request_id, answers)
    PENDING_CARDS.pop(thread_id, None)
    return web.json_response({"ok": True})


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "imbot", "pending": len(PENDING_CARDS)})


def create_app() -> web.Application:
    app = web.Application()
    app["client"] = None
    app["sse_task"] = None

    async def on_startup(app: web.Application) -> None:
        import aiohttp

        app["client"] = aiohttp.ClientSession()
        app["sse_task"] = asyncio.create_task(
            subscribe_events(app["client"], API_BASE, "default", _platform_send)
        )

    async def on_cleanup(app: web.Application) -> None:
        task = app.get("sse_task")
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await app["client"].close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/health", health)
    app.router.add_post("/webhook/feishu", handle_feishu)
    app.router.add_post("/webhook/wechat", handle_wechat)
    app.router.add_post("/webhook/action", handle_card_action)
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("IMBOT_PORT", "9091"))
    web.run_app(create_app(), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
