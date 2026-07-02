"""Shared state and utilities for route modules.

This module contains the global state variables and utility functions
that were previously defined in server.py. Route modules import from here
to avoid circular imports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from aiohttp import web

from likecodex_engine.agent.coordinator import Coordinator
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.context.session_cache import SessionContextCache
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.persistence.session import SessionStore

logger = logging.getLogger(__name__)

APP_CONFIG = web.AppKey("config", dict)

_ACTIVE_LOOPS: dict[str, AgentLoop] = {}
_ACTIVE_COORDINATORS: dict[str, Coordinator] = {}
_BACKGROUND_TASKS: set[asyncio.Task] = set()
_SESSION_STORE: SessionStore | None = None
_CONTEXT_CACHE = SessionContextCache(max_size=200)

_DEEPSEEK_TOOLS_REGISTERED: bool = False

_RESOLVED_CONFIG_CACHE: dict[int, dict] = {}
_RESOLVED_CONFIG_KEYS: tuple[str, ...] = (
    "deepseek_thinking", "api_key", "provider", "model", "base_url",
)


def _make_sse_response() -> web.StreamResponse:
    """Create a standard SSE StreamResponse."""
    return web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def _sse_write(response: web.StreamResponse, data: str) -> None:
    """Write a single SSE data event to the response."""
    try:
        await response.write(f"data: {data}\n\n".encode())
    except (ConnectionResetError, ConnectionAbortedError, OSError):
        pass


async def _sse_done(response: web.StreamResponse) -> None:
    """Write the SSE [DONE] sentinel."""
    try:
        await response.write(b"data: [DONE]\n\n")
    except (ConnectionResetError, ConnectionAbortedError, OSError):
        pass


class _SSEKeepalive:
    """Context manager for SSE keepalive heartbeat."""

    def __init__(self, response: web.StreamResponse, interval: float = 15.0):
        self._response = response
        self._interval = interval
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> _SSEKeepalive:
        async def _run() -> None:
            try:
                while not self._stop.is_set():
                    await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
                    if self._stop.is_set():
                        break
                    await self._response.write(b": keepalive\n\n")
            except TimeoutError:
                if not self._stop.is_set():
                    await self._response.write(b": keepalive\n\n")
            except Exception:
                logger.warning("SSE keepalive failed", exc_info=True)

        self._task = asyncio.create_task(_run())
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()


def _set_current_deepseek_session(loop: Any, ctx: Any, session_id: str) -> None:
    from likecodex_engine.tools.deepseek_tools import set_current_session
    set_current_session(loop, ctx, session_id)


def _session_store() -> SessionStore:
    global _SESSION_STORE
    if _SESSION_STORE is None:
        db_path = os.environ.get("LIKECODEX_SESSION_DB", ".likecodex/sessions.db")
        _SESSION_STORE = SessionStore(db_path)
    return _SESSION_STORE


def _resolve_config(app_config: dict) -> dict:
    cache_id = id(app_config)
    if cache_id in _RESOLVED_CONFIG_CACHE:
        return _RESOLVED_CONFIG_CACHE[cache_id]

    thinking_raw = app_config.get("deepseek_thinking", os.environ.get("LIKECODEX_DEEPSEEK_THINKING", "false"))
    thinking = str(thinking_raw).lower() in ("1", "true", "yes")
    api_key = (app_config.get("api_key")
               or os.environ.get("LIKECODEX_LLM_API_KEY")
               or os.environ.get("DEEPSEEK_API_KEY"))
    resolved = {
        **app_config,
        "provider": app_config.get("provider", "deepseek"),
        "model": app_config.get("model", "deepseek-v4-flash"),
        "base_url": app_config.get("base_url") or "https://api.deepseek.com",
        "api_key": api_key,
        "thinking": thinking,
    }
    _RESOLVED_CONFIG_CACHE[cache_id] = resolved
    return resolved


def _cfg_wd(request: web.Request) -> tuple[dict, str]:
    """Return (resolved_config, working_dir) from a web request."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    return cfg, cfg.get("working_dir", ".")


def _merge_request_config(cfg: dict, data: dict) -> dict:
    """Override config with api_key and model from request body (if present)."""
    merged = dict(cfg)
    api_key = data.get("api_key") or cfg.get("api_key")
    model = data.get("model") or cfg.get("model")
    if api_key and api_key != cfg.get("api_key"):
        merged["api_key"] = api_key
    if model and model != cfg.get("model"):
        merged["model"] = model
    return merged


def _serialize_response(resp) -> dict:
    payload = {
        "type": resp.event_type,
        "content": resp.content,
        "tool_calls": [tc.model_dump() for tc in resp.tool_calls],
        "model": resp.model,
    }
    if resp.usage:
        payload["usage"] = resp.usage
    if resp.metadata:
        payload["metadata"] = resp.metadata
    return payload


async def _run_manual_compact(
    context: ContextManager,
    llm: Any,
    focus: str,
) -> AsyncIterator[LLMResponse]:
    from likecodex_engine.server_turn import run_manual_compact_responses
    async for resp in run_manual_compact_responses(context, llm, focus):
        yield resp


def _get_or_create_context(session_id: str, store: SessionStore) -> ContextManager:
    cached = _CONTEXT_CACHE.get(session_id)
    if cached is not None:
        return cached

    restored = store.restore_context_manager(session_id)
    if restored is not None:
        _CONTEXT_CACHE.put(session_id, restored)
        return restored

    context = ContextManager()
    _CONTEXT_CACHE.put(session_id, context)
    return context


def _get_runner(session_id: str) -> AgentLoop | Coordinator:
    if session_id in _ACTIVE_COORDINATORS:
        return _ACTIVE_COORDINATORS[session_id]
    return _ACTIVE_LOOPS[session_id]


def _resolve_loop(session_id: str) -> AgentLoop | None:
    runner = _ACTIVE_LOOPS.get(session_id)
    if runner is not None:
        return runner
    coord = _ACTIVE_COORDINATORS.get(session_id)
    return coord.executor if coord else None
