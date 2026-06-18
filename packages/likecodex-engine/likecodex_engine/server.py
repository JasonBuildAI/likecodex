"""HTTP bridge server exposing the Python agent engine."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from aiohttp import web

from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.planner import Planner
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.context.session_cache import SessionContextCache
from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.llm.factory import create_provider
from likecodex_engine.mcp.loader import register_mcp_tools
from likecodex_engine.memory.vector import VectorMemory
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.persistence.session import SessionEvent, SessionStore
from likecodex_engine.tools.registry import ToolRegistry

_ACTIVE_LOOPS: dict[str, AgentLoop] = {}
_SESSION_STORE: SessionStore | None = None
_CONTEXT_CACHE = SessionContextCache()


def _session_store() -> SessionStore:
    global _SESSION_STORE
    if _SESSION_STORE is None:
        db_path = os.environ.get("LIKECODEX_SESSION_DB", ".likecodex/sessions.db")
        _SESSION_STORE = SessionStore(db_path)
    return _SESSION_STORE


def _resolve_config(app_config: dict) -> dict:
    thinking_raw = app_config.get("deepseek_thinking", os.environ.get("LIKECODEX_DEEPSEEK_THINKING", "false"))
    thinking = str(thinking_raw).lower() in ("1", "true", "yes")
    api_key = app_config.get("api_key") or os.environ.get("LIKECODEX_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    return {
        **app_config,
        "provider": app_config.get("provider", "deepseek"),
        "model": app_config.get("model", "deepseek-v4-flash"),
        "base_url": app_config.get("base_url") or "https://api.deepseek.com",
        "api_key": api_key,
        "thinking": thinking,
    }


async def health(request: web.Request) -> web.Response:
    metrics = global_cache_metrics().to_dict()
    return web.json_response({"status": "ok", "provider": "deepseek", "cache": metrics})


async def metrics(request: web.Request) -> web.Response:
    return web.json_response(global_cache_metrics().to_dict())


def _serialize_response(resp) -> dict:
    payload = {
        "type": resp.event_type,
        "content": resp.content,
        "tool_calls": [tc.model_dump() for tc in resp.tool_calls],
        "model": resp.model,
    }
    if resp.usage:
        payload["usage"] = resp.usage
    return payload


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


def _make_agent(
    config: dict,
    enable_planner: bool | None = None,
    session_id: str | None = None,
    context: ContextManager | None = None,
) -> AgentLoop:
    cfg = _resolve_config(config)
    working_dir = cfg.get("working_dir", ".")
    llm = create_provider(
        cfg.get("provider", "deepseek"),
        cfg.get("model", "deepseek-v4-flash"),
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=bool(cfg.get("thinking", False)),
    )
    tools = ToolRegistry(working_dir)
    memory = VectorMemory(cfg.get("memory_path", ".likecodex/memory.jsonl"))
    approval_mode = cfg.get("approval_mode", "auto")
    evaluator = PermissionEvaluator(ApprovalMode(approval_mode))
    if enable_planner is None:
        enable_planner = str(cfg.get("enable_planner", "false")).lower() in ("1", "true", "yes")
    planner = Planner(llm) if enable_planner else None

    store = _session_store()
    sid = session_id or str(uuid.uuid4())
    store.create_session(sid, {"working_dir": working_dir})

    if context is None:
        context = _get_or_create_context(sid, store)

    def on_event(resp) -> None:
        metadata: dict = {"model": resp.model, **(resp.metadata or {})}
        if resp.event_type == "assistant" and resp.tool_calls:
            from likecodex_engine.context.manager import stable_json_dumps, stable_tool_calls_json

            tool_payload = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": stable_json_dumps(tc.arguments),
                    },
                }
                for tc in resp.tool_calls
            ]
            metadata["tool_calls"] = tool_payload
            metadata["raw_tool_calls"] = stable_tool_calls_json(tool_payload)
        if resp.usage:
            metadata["usage"] = resp.usage
        store.append_event(
            sid,
            SessionEvent(
                event_type=resp.event_type,
                content=resp.content,
                metadata=metadata,
            ),
        )

    def agent_factory() -> AgentLoop:
        return _make_agent(cfg, enable_planner=enable_planner, session_id=sid, context=ContextManager())

    loop = AgentLoop(
        llm,
        tools,
        context,
        planner=planner,
        permission_evaluator=evaluator,
        sandbox_executor_url=cfg.get("sandbox_executor_url"),
        memory=memory,
        session_id=sid,
        on_event=on_event,
        agent_factory=agent_factory,
    )
    _ACTIVE_LOOPS[sid] = loop
    return loop


async def _ensure_mcp(config: dict, tools: ToolRegistry) -> None:
    if str(config.get("enable_mcp", "false")).lower() in ("1", "true", "yes"):
        await register_mcp_tools(tools, config)


async def chat(request: web.Request) -> web.StreamResponse:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    cfg = _resolve_config(request.app["config"])

    sid = session_id or str(uuid.uuid4())
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context)
    await _ensure_mcp(cfg, loop.tools)
    store.append_event(sid, SessionEvent(event_type="user", content=prompt, metadata={}))

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": sid,
        },
    )
    await response.prepare(request)

    async for resp in loop.run(prompt):
        payload = json.dumps(_serialize_response(resp))
        await response.write(f"data: {payload}\n\n".encode())
    cache_stats = global_cache_metrics().to_dict()
    await response.write(f"data: {json.dumps({'type': 'cache_stats', 'content': '', 'cache': cache_stats})}\n\n".encode())
    await response.write(b"data: [DONE]\n\n")
    return response


async def run_task(request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    cfg = _resolve_config(request.app["config"])

    sid = session_id or str(uuid.uuid4())
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context)
    await _ensure_mcp(cfg, loop.tools)
    store.append_event(sid, SessionEvent(event_type="user", content=prompt, metadata={}))

    outputs = []
    async for resp in loop.run(prompt):
        outputs.append(_serialize_response(resp))

    return web.json_response({"outputs": outputs, "session_id": sid, "cache": global_cache_metrics().to_dict()})


async def plan_task(request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    cfg = _resolve_config(request.app["config"])

    llm = create_provider(
        cfg.get("provider", "deepseek"),
        cfg.get("model", "deepseek-v4-flash"),
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=bool(cfg.get("thinking", False)),
    )
    planner = Planner(llm)
    plan = await planner.plan(str(uuid.uuid4()), prompt)

    return web.json_response(
        {
            "task_id": plan.task_id,
            "reasoning": plan.reasoning,
            "steps": [
                {
                    "id": s.id,
                    "description": s.description,
                    "status": s.status.value,
                    "depends_on": s.depends_on,
                }
                for s in plan.steps
            ],
        }
    )


async def create_task(request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    cfg = _resolve_config(request.app["config"])
    task_id = session_id or str(uuid.uuid4())

    store = _session_store()
    store.create_session(task_id, {"prompt": prompt, "status": "running"})

    async def run_in_background() -> None:
        context = _get_or_create_context(task_id, store)
        loop = _make_agent(cfg, session_id=task_id, context=context)
        await _ensure_mcp(cfg, loop.tools)
        try:
            async for resp in loop.run(prompt):
                payload = _serialize_response(resp)
                metadata = {"model": resp.model}
                if resp.usage:
                    metadata["usage"] = resp.usage
                store.append_event(
                    task_id,
                    SessionEvent(
                        event_type=resp.event_type,
                        content=resp.content,
                        metadata=metadata,
                    ),
                )
            store.create_session(task_id, {"prompt": prompt, "status": "completed"})
        except Exception as e:
            store.create_session(task_id, {"prompt": prompt, "status": "failed"})
            store.append_event(
                task_id,
                SessionEvent(event_type="error", content=str(e), metadata={}),
            )
        finally:
            _ACTIVE_LOOPS.pop(task_id, None)

    asyncio.create_task(run_in_background())

    return web.json_response({"task_id": task_id, "status": "running", "session_id": task_id})


async def get_task(request: web.Request) -> web.Response:
    task_id = request.match_info["task_id"]
    store = _session_store()
    metadata = store.get_session_metadata(task_id)
    if not metadata:
        return web.json_response({"error": "Task not found"}, status=404)
    events = store.list_events(task_id)
    status = metadata.get("status", "running")
    outputs = [
        {
            "type": e.event_type,
            "content": e.content,
            "model": e.metadata.get("model", ""),
            "tool_calls": e.metadata.get("tool_calls", []),
            "usage": e.metadata.get("usage"),
        }
        for e in events
    ]
    return web.json_response(
        {
            "prompt": metadata.get("prompt", ""),
            "status": status,
            "outputs": outputs,
            "cache": global_cache_metrics().to_dict(),
        }
    )


async def list_pending_permissions(request: web.Request) -> web.Response:
    pending = []
    for loop in _ACTIVE_LOOPS.values():
        pending.extend(loop.list_pending_permissions())
    return web.json_response({"pending": pending})


async def respond_permission(request: web.Request) -> web.Response:
    request_id = request.match_info["id"]
    data = await request.json()
    approved = bool(data.get("approved", False))
    for loop in _ACTIVE_LOOPS.values():
        if await loop.respond_permission(request_id, approved):
            return web.json_response({"ok": True, "request_id": request_id, "approved": approved})
    return web.json_response({"error": "Permission request not found"}, status=404)


async def list_sessions(request: web.Request) -> web.Response:
    sessions = _session_store().list_sessions()
    return web.json_response({"sessions": sessions})


async def get_session_events(request: web.Request) -> web.Response:
    session_id = request.match_info["id"]
    events = _session_store().list_events(session_id)
    if not events:
        return web.json_response({"error": "Session not found"}, status=404)
    return web.json_response(
        {
            "session_id": session_id,
            "events": [
                {
                    "event_type": e.event_type,
                    "content": e.content,
                    "metadata": e.metadata,
                    "timestamp": e.timestamp,
                }
                for e in events
            ],
        }
    )


def create_app(config: dict | None = None) -> web.Application:
    app = web.Application()
    app["config"] = config or {}
    app.router.add_get("/health", health)
    app.router.add_get("/metrics", metrics)
    app.router.add_post("/chat", chat)
    app.router.add_post("/run", run_task)
    app.router.add_post("/plan", plan_task)
    app.router.add_post("/tasks", create_task)
    app.router.add_get("/tasks/{task_id}", get_task)
    app.router.add_get("/permissions/pending", list_pending_permissions)
    app.router.add_post("/permissions/{id}/respond", respond_permission)
    app.router.add_get("/sessions", list_sessions)
    app.router.add_get("/sessions/{id}/events", get_session_events)
    return app


def main() -> None:
    host = os.environ.get("LIKECODEX_ENGINE_HOST", "127.0.0.1")
    port = int(os.environ.get("LIKECODEX_ENGINE_PORT", "9090"))
    working_dir = os.environ.get("LIKECODEX_WORKING_DIR", str(Path.cwd()))
    config = {
        "provider": os.environ.get("LIKECODEX_LLM_PROVIDER", "deepseek"),
        "model": os.environ.get("LIKECODEX_LLM_MODEL", "deepseek-v4-flash"),
        "api_key": os.environ.get("LIKECODEX_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
        "base_url": os.environ.get("LIKECODEX_LLM_BASE_URL", "https://api.deepseek.com"),
        "deepseek_thinking": os.environ.get("LIKECODEX_DEEPSEEK_THINKING", "false"),
        "working_dir": working_dir,
        "approval_mode": os.environ.get("LIKECODEX_APPROVAL_MODE", "auto"),
        "enable_planner": os.environ.get("LIKECODEX_ENABLE_PLANNER", "false"),
        "enable_mcp": os.environ.get("LIKECODEX_ENABLE_MCP", "false"),
        "sandbox_executor_url": os.environ.get("LIKECODEX_SANDBOX_URL"),
        "memory_path": os.environ.get("LIKECODEX_MEMORY_PATH", ".likecodex/memory.jsonl"),
    }
    app = create_app(config)
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    main()
