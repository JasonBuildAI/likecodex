"""HTTP bridge server exposing the Python agent engine."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from aiohttp import web

from likecodex_engine.agent.checkpoints import CheckpointManager
from likecodex_engine.agent.commands import expand_prompt
from likecodex_engine.agent.coordinator import Coordinator
from likecodex_engine.agent.loop import AgentLoop, build_subagent_loop
from likecodex_engine.agent.plan_state import PlanState
from likecodex_engine.agent.planner import Planner
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.context.project_memory import load_project_memory
from likecodex_engine.context.session_cache import SessionContextCache
from likecodex_engine.context.session_resolver import session_id_for_dir
from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.factory import create_provider
from likecodex_engine.mcp.loader import register_mcp_tools
from likecodex_engine.memory.vector import VectorMemory
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.permissions.policy import Policy
from likecodex_engine.persistence.session import SessionEvent, SessionStore
from likecodex_engine.skills.loader import discover_skills, skills_prefix_block
from likecodex_engine.tools.registry import ToolRegistry

_ACTIVE_LOOPS: dict[str, AgentLoop] = {}
_ACTIVE_COORDINATORS: dict[str, Coordinator] = {}
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
    if resp.metadata:
        payload["metadata"] = resp.metadata
    return payload


async def _run_manual_compact(
    context: ContextManager,
    llm: Any,
    focus: str,
) -> AsyncIterator[LLMResponse]:
    """Run a manual /compact pass, yielding compaction + assistant events."""
    if hasattr(context, "set_compact_llm"):
        context.set_compact_llm(llm)
    if not hasattr(context, "compact_async"):
        yield LLMResponse(
            content="Compaction is not available for this session context.",
            model="command",
            event_type="assistant",
        )
        return

    yield LLMResponse(
        content=json.dumps({"trigger": "manual", "focus": focus}),
        model="system",
        event_type="compaction_started",
    )
    info = await context.compact_async(instructions=focus, force=True)
    yield LLMResponse(
        content=json.dumps(info),
        model="system",
        event_type="compaction_done",
    )
    if info.get("compacted"):
        reply = "Context compacted."
        if focus:
            reply += f" Focus: {focus}"
    else:
        reply = "Nothing to compact."
    yield LLMResponse(content=reply, model="command", event_type="assistant")


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


def _make_agent(
    config: dict,
    enable_planner: bool | None = None,
    session_id: str | None = None,
    context: ContextManager | None = None,
    no_tools: bool = False,
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
    policy = Policy.from_config(cfg)
    evaluator = PermissionEvaluator(ApprovalMode(approval_mode), policy, working_dir)
    planner = None
    if enable_planner is None:
        enable_planner = str(cfg.get("enable_planner", "false")).lower() in ("1", "true", "yes")
    planner_model = cfg.get("planner_model") or "deepseek-v4-pro"
    planner_llm = create_provider(
        cfg.get("provider", "deepseek"),
        planner_model,
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=bool(cfg.get("thinking", False)),
    ) if enable_planner else None

    store = _session_store()
    sid = session_id or session_id_for_dir(working_dir)
    store.create_session(sid, {"working_dir": working_dir})

    if context is None:
        context = _get_or_create_context(sid, store)

    skills = discover_skills(working_dir)
    context.set_skills_content(skills_prefix_block(skills))
    if hasattr(context, "set_project_memories"):
        memory_parts: list[str] = []
        file_memory = load_project_memory(working_dir)
        if file_memory:
            memory_parts.append(file_memory)
        project_memories = memory.list_by_type("project", limit=10)
        if project_memories:
            memory_parts.append("\n".join(f"- {m.get('text', '')}" for m in project_memories))
        if memory_parts:
            context.set_project_memories("\n\n".join(memory_parts))

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

    def agent_factory(tool_whitelist: list[str] | None = None, max_steps: int | None = None) -> AgentLoop:
        return build_subagent_loop(loop_holder["loop"], tool_whitelist, max_steps)

    loop_holder: dict[str, AgentLoop] = {}

    loop = AgentLoop(
        llm,
        tools,
        context,
        max_iterations=int(cfg.get("max_steps", 50)),
        planner=planner,
        permission_evaluator=evaluator,
        sandbox_executor_url=cfg.get("sandbox_executor_url"),
        memory=memory,
        session_id=sid,
        on_event=on_event,
        agent_factory=agent_factory,
        no_tools=no_tools,
        plan_state=PlanState(),
    )
    loop_holder["loop"] = loop
    tools.set_agent_factory(agent_factory)
    tools.set_session_log_provider(lambda: loop.context.messages)
    tools.set_session_id(sid)
    _ACTIVE_LOOPS[sid] = loop
    if enable_planner and planner_llm is not None:
        planning_context = context.prefix.project_memories if hasattr(context, "prefix") else ""
        coordinator = Coordinator(
            loop,
            planner_llm,
            planner_max_steps=int(cfg.get("planner_max_steps", 20)),
            planning_context=planning_context,
        )
        _ACTIVE_COORDINATORS[sid] = coordinator
    return loop


async def _ensure_mcp(config: dict, tools: ToolRegistry) -> None:
    if str(config.get("enable_mcp", "false")).lower() in ("1", "true", "yes"):
        await register_mcp_tools(tools, config)


async def chat(request: web.Request) -> web.StreamResponse:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    no_tools = bool(data.get("no_tools", False))
    cfg = _resolve_config(request.app["config"])
    working_dir = cfg.get("working_dir", ".")

    sid = session_id or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context, no_tools=no_tools)
    await _ensure_mcp(cfg, loop.tools)
    store.append_event(sid, SessionEvent(event_type="user", content=prompt, metadata={}))

    expanded = expand_prompt(prompt, working_dir)

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

    if expanded.compact_trigger:
        async for resp in _run_manual_compact(context, loop.llm, expanded.compact_focus):
            payload = json.dumps(_serialize_response(resp))
            await response.write(f"data: {payload}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
        return response

    if expanded.direct_reply is not None:
        reply = {"type": "assistant", "content": expanded.direct_reply, "tool_calls": [], "model": "command"}
        await response.write(f"data: {json.dumps(reply)}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
        return response

    for block in expanded.context_blocks:
        context.add_context_block(block)

    runner = _get_runner(sid)

    if expanded.plan_mode_enter:
        runner.plan_state.enter()
    if expanded.plan_mode_exit_request:
        runner.plan_state.request_exit(expanded.prompt)
    if expanded.plan_mode_exit_approve:
        runner.plan_state.approve_exit()

    async for resp in runner.run(expanded.prompt):
        payload = json.dumps(_serialize_response(resp))
        await response.write(f"data: {payload}\n\n".encode())
    cache_stats = global_cache_metrics().to_dict()
    cache_event = json.dumps({"type": "cache_stats", "content": "", "cache": cache_stats})
    await response.write(f"data: {cache_event}\n\n".encode())
    await response.write(b"data: [DONE]\n\n")
    return response


async def run_task(request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    cfg = _resolve_config(request.app["config"])
    working_dir = cfg.get("working_dir", ".")

    sid = session_id or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context)
    await _ensure_mcp(cfg, loop.tools)
    store.append_event(sid, SessionEvent(event_type="user", content=prompt, metadata={}))

    expanded = expand_prompt(prompt, working_dir)
    if expanded.compact_trigger:
        outputs = []
        async for resp in _run_manual_compact(context, loop.llm, expanded.compact_focus):
            outputs.append(_serialize_response(resp))
        return web.json_response({"outputs": outputs, "session_id": sid})
    if expanded.direct_reply is not None:
        reply = {"type": "assistant", "content": expanded.direct_reply, "tool_calls": [], "model": "command"}
        return web.json_response({"outputs": [reply], "session_id": sid})
    for block in expanded.context_blocks:
        context.add_context_block(block)

    runner = _get_runner(sid)

    outputs = []
    async for resp in runner.run(expanded.prompt):
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
    task_id = session_id or session_id_for_dir(cfg.get("working_dir", "."))

    store = _session_store()
    store.create_session(task_id, {"prompt": prompt, "status": "running"})

    async def run_in_background() -> None:
        context = _get_or_create_context(task_id, store)
        loop = _make_agent(cfg, session_id=task_id, context=context)
        await _ensure_mcp(cfg, loop.tools)
        try:
            async for resp in loop.run(prompt):
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
    pending: list[dict] = []
    seen: set[str] = set()
    for sid in set(_ACTIVE_LOOPS) | set(_ACTIVE_COORDINATORS):
        runner = _get_runner(sid)
        for item in runner.list_pending_permissions():
            rid = item.get("request_id")
            if rid and rid not in seen:
                seen.add(rid)
                pending.append(item)
    return web.json_response({"pending": pending})


async def respond_permission(request: web.Request) -> web.Response:
    request_id = request.match_info["id"]
    data = await request.json()
    approved = bool(data.get("approved", False))
    for sid in list(_ACTIVE_LOOPS.keys()) + list(_ACTIVE_COORDINATORS.keys()):
        runner = _get_runner(sid)
        if await runner.respond_permission(request_id, approved):
            return web.json_response({"ok": True, "request_id": request_id, "approved": approved})
    return web.json_response({"error": "Permission request not found"}, status=404)


async def list_checkpoints(request: web.Request) -> web.Response:
    cfg = _resolve_config(request.app["config"])
    manager = CheckpointManager(cfg.get("working_dir", "."))
    return web.json_response({"checkpoints": [c.to_dict() for c in manager.list_checkpoints()]})


async def codegraph_search(request: web.Request) -> web.Response:
    pattern = request.query.get("pattern", "")
    cfg = _resolve_config(request.app["config"])
    working_dir = cfg.get("working_dir", ".")
    from likecodex_engine.tools.codegraph import load_or_build

    graph = load_or_build(working_dir)
    results = []
    for sym in graph.symbols:
        if pattern.lower() in sym.name.lower():
            results.append(
                {
                    "name": sym.name,
                    "kind": sym.kind,
                    "path": sym.path,
                    "line": sym.line,
                }
            )
            if len(results) >= 50:
                break
    return web.json_response(
        {"pattern": pattern, "results": results, "files": graph.file_count}
    )


async def rewind_checkpoint(request: web.Request) -> web.Response:
    data = await request.json()
    checkpoint_id = data.get("checkpoint_id")
    cfg = _resolve_config(request.app["config"])
    manager = CheckpointManager(cfg.get("working_dir", "."))
    result = manager.rewind(checkpoint_id)
    status = 200 if result.get("rewound") else 400
    return web.json_response(result, status=status)


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
    app.router.add_get("/checkpoints", list_checkpoints)
    app.router.add_post("/checkpoints/rewind", rewind_checkpoint)
    app.router.add_get("/codegraph/search", codegraph_search)
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
        "planner_model": os.environ.get("LIKECODEX_PLANNER_MODEL", "deepseek-v4-pro"),
        "compact_ratio": os.environ.get("LIKECODEX_COMPACT_RATIO", "0.8"),
    }
    app = create_app(config)
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    main()
