"""DeepSeek-specific API route handlers.

Handles: cache stats, switch model, session cost, diagnostics.
"""

from __future__ import annotations

import json
import logging
import os

from aiohttp import web

from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.llm.deepseek import DeepSeekProvider, DeepSeekUsage
from likecodex_engine.llm.factory import create_provider

from likecodex_engine.routes._shared import (
    _resolve_config,
    _cfg_wd,
    _resolve_loop,
    _get_or_create_context,
    _DEEPSEEK_TOOLS_REGISTERED,
    _session_store,
    APP_CONFIG,
)

logger = logging.getLogger(__name__)


async def deepseek_cache_stats(request: web.Request) -> web.Response:
    metrics = global_cache_metrics()
    from likecodex_engine.context.cache_shape import capture_prefix_shape
    shape = capture_prefix_shape()
    return web.json_response({
        "hit_rate": metrics.hit_rate,
        "recent_hit_rate": metrics.recent_hit_rate,
        "request_count": metrics.request_count,
        "total_hit_tokens": metrics.total_hit_tokens,
        "total_miss_tokens": metrics.total_miss_tokens,
        "prefix_shape": shape,
    })


async def deepseek_api_switch_model(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    model = data.get("model", "")
    if not session_id:
        return web.json_response({"error": "session_id is required"}, status=400)
    loop = _resolve_loop(session_id)
    if loop is None:
        return web.json_response({"error": "Session not found"}, status=404)
    valid = {"deepseek-v4-flash", "deepseek-v4-pro", "flash", "pro"}
    if model not in valid:
        return web.json_response({"error": f"Invalid model '{model}'. Valid: {sorted(valid)}"}, status=400)
    model_map = {"flash": "deepseek-v4-flash", "pro": "deepseek-v4-pro"}
    resolved = model_map.get(model, model)
    old_model = getattr(loop.llm, "model", "unknown")
    loop.llm = create_provider(provider="deepseek", model=resolved)
    return web.json_response({"ok": True, "session_id": session_id, "switched_from": old_model, "switched_to": resolved})


async def deepseek_session_cost(request: web.Request) -> web.Response:
    session_id = request.query.get("session_id", "")
    if not session_id:
        cfg = _resolve_config(request.app[APP_CONFIG])
        working_dir = cfg.get("working_dir", ".")
        from likecodex_engine.context.session_resolver import session_id_for_dir
        session_id = session_id_for_dir(working_dir)
    metrics = global_cache_metrics()
    usage = DeepSeekUsage(
        prompt_tokens=metrics.total_hit_tokens + metrics.total_miss_tokens,
        completion_tokens=0,
        cache_hit_tokens=metrics.total_hit_tokens,
        cache_miss_tokens=metrics.total_miss_tokens,
        model="deepseek-v4-flash",
    )
    return web.json_response({
        "session_id": session_id,
        "cache_metrics": {"hit_rate": round(metrics.hit_rate, 4), "total_requests": metrics.request_count},
        "cost": {"input_cost": round(usage.input_cost, 6), "output_cost": round(usage.output_cost, 6), "total_cost": round(usage.total_cost, 6), "currency": "USD"},
        "usage": {"cache_hit_tokens": metrics.total_hit_tokens, "cache_miss_tokens": metrics.total_miss_tokens, "cache_hit_rate": round(usage.cache_hit_rate, 4), "reasoning_tokens": 0},
    })


async def deepseek_diagnostics(request: web.Request) -> web.Response:
    session_id = request.query.get("session_id", "")
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    from likecodex_engine.context.session_resolver import session_id_for_dir
    sid = session_id or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(sid, store)
    from likecodex_engine.context.cache_shape import capture_prefix_shape
    system_prompt = DeepSeekProvider.load_system_prompt()
    has_custom_prompt = bool(system_prompt)
    shape = {}
    if hasattr(context, "capture_prefix_shape"):
        shape = capture_prefix_shape(
            context.prefix.combined if hasattr(context, "prefix") else "",
            [], getattr(context, "rewrite_version", 0),
        )
    return web.json_response({
        "session_id": sid,
        "provider": cfg.get("provider", "deepseek"),
        "system_prompt": {"has_custom_deepseek_prompt": has_custom_prompt, "length": len(system_prompt) if has_custom_prompt else 0, "source": "deepseek_v4_system.txt" if has_custom_prompt else "default"},
        "cache": {"prefix_stable": shape.get("stable", True) if shape else None, "rewrite_version": getattr(context, "rewrite_version", 0), "log_size": len(getattr(context, "messages", []))},
        "deepseek_tools_registered": _DEEPSEEK_TOOLS_REGISTERED,
        "config": {"api_key_set": bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LIKECODEX_LLM_API_KEY"))},
    })


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_get("/api/deepseek/cache-stats", deepseek_cache_stats)
    app.router.add_post("/api/deepseek/switch-model", deepseek_api_switch_model)
    app.router.add_get("/api/deepseek/session-cost", deepseek_session_cost)
    app.router.add_get("/api/deepseek/diagnostics", deepseek_diagnostics)
