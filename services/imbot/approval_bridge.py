"""Bridge LikeCodex permission/ask SSE events to IM platform callbacks."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

log = logging.getLogger("imbot.bridge")

PlatformSender = Callable[[str, dict[str, Any]], Awaitable[None]]


async def subscribe_events(
    client: aiohttp.ClientSession,
    api_base: str,
    thread_id: str,
    on_card: PlatformSender,
) -> None:
    """Subscribe to Rust control plane SSE and forward permission/ask as cards."""
    url = f"{api_base.rstrip('/')}/events"
    while True:
        try:
            async with client.get(url, timeout=None) as resp:
                if resp.status != 200:
                    await asyncio.sleep(2)
                    continue
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    await _handle_event(client, api_base, thread_id, event, on_card)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("SSE reconnect after error: %s", exc)
            await asyncio.sleep(2)


async def _handle_event(
    client: aiohttp.ClientSession,
    api_base: str,
    thread_id: str,
    event: dict[str, Any],
    on_card: PlatformSender,
) -> None:
    etype = str(event.get("type", ""))
    payload = event.get("payload") or {}

    if etype == "permission_requested":
        req = payload.get("request") or {}
        desc = req.get("description") or ""
        parsed: dict[str, Any] = {}
        if isinstance(desc, str) and desc.startswith("{"):
            try:
                parsed = json.loads(desc)
            except json.JSONDecodeError:
                parsed = {"description": desc}
        request_id = parsed.get("request_id") or req.get("id") or ""
        tool = parsed.get("tool") or "tool"
        await on_card(
            thread_id,
            {
                "kind": "permission",
                "request_id": request_id,
                "tool": tool,
                "actions": [
                    {"label": "Allow once", "grant_scope": "once", "approved": True},
                    {"label": "Allow session", "grant_scope": "session", "approved": True},
                    {"label": "Deny", "grant_scope": "once", "approved": False},
                ],
            },
        )
        return

    if etype == "ask_requested":
        req = payload.get("request") or {}
        await on_card(
            thread_id,
            {
                "kind": "ask",
                "request_id": req.get("id") or "",
                "question": req.get("question") or "Choose:",
                "options": req.get("options") or [],
                "multi_select": bool(req.get("multi_select")),
            },
        )


async def respond_permission(
    client: aiohttp.ClientSession,
    api_base: str,
    request_id: str,
    approved: bool,
    grant_scope: str = "once",
) -> None:
    await client.post(
        f"{api_base.rstrip('/')}/permissions/{request_id}/respond",
        json={"approved": approved, "grant_scope": grant_scope},
    )


async def respond_ask(
    client: aiohttp.ClientSession,
    api_base: str,
    request_id: str,
    answers: list[dict[str, Any]],
) -> None:
    await client.post(
        f"{api_base.rstrip('/')}/ask/{request_id}/respond",
        json={"answers": answers},
    )
