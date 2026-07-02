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
    session_id = request.query.get("session_id", "")
    metrics = global_cache_metrics()
    from likecodex_engine.context.cache_shape import capture_prefix_shape
    shape = capture_prefix_shape()

    # Calculate cache efficiency
    total_tokens = metrics.total_hit_tokens + metrics.total_miss_tokens
    cache_size_estimate = shape.get("prefix_length", 0) if shape else 0
    entry_count = metrics.request_count

    # Cache efficiency recommendations
    recommendations: list[str] = []
    if metrics.hit_rate < 0.3:
        recommendations.append(
            "Cache hit rate is low. Consider keeping system prompts stable, "
            "avoiding frequent tool schema changes."
        )
    elif metrics.hit_rate < 0.6:
        recommendations.append(
            "Moderate hit rate. Session should improve with more turns."
        )
    elif metrics.hit_rate >= 0.8:
        recommendations.append(
            "Excellent cache efficiency! Continue maintaining stable prefix."
        )
    if metrics.cache_reset_count > 5:
        recommendations.append(
            f"High cache reset count ({metrics.cache_reset_count}). "
            "Consider reducing system prompt changes."
        )
    if not recommendations:
        recommendations.append("Cache health is good, no optimization needed.")

    # Per-session cache stats (if session_id provided)
    session_stats = None
    if session_id:
        from likecodex_engine.llm.cost_tracker import get_cost_tracker
        tracker = get_cost_tracker()
        record = tracker.get_session_cost(session_id)
        if record:
            session_stats = {
                "session_id": session_id,
                "request_count": record.request_count,
                "total_cache_hit_tokens": record.total_cache_hit_tokens,
                "total_cache_miss_tokens": record.total_cache_miss_tokens,
                "overall_cache_hit_rate": round(record.overall_cache_hit_rate, 4),
                "total_cost": record.total_cost,
            }

    return web.json_response({
        "hit_rate": metrics.hit_rate,
        "recent_hit_rate": metrics.recent_hit_rate,
        "request_count": metrics.request_count,
        "total_hit_tokens": metrics.total_hit_tokens,
        "total_miss_tokens": metrics.total_miss_tokens,
        "cache_reset_count": metrics.cache_reset_count,
        "cache_size_estimate": cache_size_estimate,
        "entry_count": entry_count,
        "prefix_shape": shape,
        "session_stats": session_stats,
        "recommendations": recommendations,
        "efficiency_score": _calc_efficiency_score(metrics),
    })


def _calc_efficiency_score(metrics: Any) -> dict[str, float]:
    """Calculate cache efficiency score (0-100)."""
    hit_score = metrics.hit_rate * 60  # 60 points for hit rate
    stability_score = max(0, 20 - metrics.cache_reset_count * 2)  # 20 points for stability
    volume_score = min(20, metrics.request_count * 2)  # 20 points for volume
    total = hit_score + stability_score + volume_score
    return {
        "score": round(total, 1),
        "hit_rate_component": round(hit_score, 1),
        "stability_component": round(stability_score, 1),
        "volume_component": round(volume_score, 1),
    }


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

    from likecodex_engine.llm.cost_tracker import get_cost_tracker
    tracker = get_cost_tracker()
    record = tracker.get_session_cost(session_id)

    if record:
        cost_data = record.to_dict()
    else:
        # Build from cache metrics as fallback
        metrics = global_cache_metrics()
        cost_data = {
            "session_id": session_id,
            "request_count": metrics.request_count,
            "total_tokens": metrics.total_hit_tokens + metrics.total_miss_tokens,
            "total_input_tokens": metrics.total_hit_tokens + metrics.total_miss_tokens,
            "total_output_tokens": 0,
            "total_input_cost": round(metrics.total_hit_tokens / 1_000_000 * 0.01, 8),
            "total_output_cost": 0,
            "total_cost": round(metrics.total_hit_tokens / 1_000_000 * 0.01, 8),
            "total_cache_hit_tokens": metrics.total_hit_tokens,
            "total_cache_miss_tokens": metrics.total_miss_tokens,
            "overall_cache_hit_rate": round(metrics.hit_rate, 4),
            "model_switch_count": 0,
            "created_at": 0,
            "updated_at": 0,
            "duration_seconds": 0,
        }

    return web.json_response(cost_data)


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
