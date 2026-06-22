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
from likecodex_engine.agent.coordinator import Coordinator
from likecodex_engine.agent.loop import AgentLoop, build_subagent_loop
from likecodex_engine.agent.plan_state import PlanState
from likecodex_engine.agent.planner import Planner
from likecodex_engine.config_loader import engine_config_from_env
from likecodex_engine.context.instruction import load_host_checks_from_dir
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.context.project_memory import load_project_memory
from likecodex_engine.context.session_cache import SessionContextCache
from likecodex_engine.context.session_resolver import session_id_for_dir
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.llm.factory import create_provider
from likecodex_engine.mcp.loader import register_mcp_tools
from likecodex_engine.memory.vector import VectorMemory
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.permissions.policy import Policy
from likecodex_engine.persistence.session import SessionEvent, SessionStore
from likecodex_engine.server_turn import prepare_turn, run_manual_compact_responses
from likecodex_engine.skills.loader import discover_skills, skills_prefix_block
from likecodex_engine.tools.registry import ToolRegistry

# Web UI static files directory
STATIC_DIR = Path(__file__).parent / "static"
LITE_HTML = STATIC_DIR / "lite" / "index.html"

APP_CONFIG = web.AppKey("config", dict)

_ACTIVE_LOOPS: dict[str, AgentLoop] = {}
_ACTIVE_COORDINATORS: dict[str, Coordinator] = {}
_SESSION_STORE: SessionStore | None = None
_CONTEXT_CACHE = SessionContextCache()

# Track whether DeepSeek tools have been registered
_DEEPSEEK_TOOLS_REGISTERED: bool = False


def _set_current_deepseek_session(loop: Any, ctx: Any, session_id: str) -> None:
    """Set the current session context for DeepSeek tools."""
    from likecodex_engine.tools.deepseek_tools import set_current_session

    set_current_session(loop, ctx, session_id)


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
        reasoning_effort=str(cfg.get("reasoning_effort", "")),
    )
    tools = ToolRegistry(working_dir, config=cfg)
    memory = VectorMemory(cfg.get("memory_path", ".likecodex/memory.jsonl"))
    approval_mode = cfg.get("approval_mode", "auto")
    policy = Policy.from_config(cfg)
    evaluator = PermissionEvaluator(ApprovalMode(approval_mode), policy, working_dir)
    planner = None
    if enable_planner is None:
        enable_planner = str(cfg.get("enable_planner", "false")).lower() in ("1", "true", "yes")
    planner_model = cfg.get("planner_model") or "deepseek-v4-pro"
    planner_llm = (
        create_provider(
            cfg.get("provider", "deepseek"),
            planner_model,
            cfg.get("api_key"),
            cfg.get("base_url"),
            thinking=bool(cfg.get("thinking", False)),
            reasoning_effort=str(cfg.get("reasoning_effort", "")),
        )
        if enable_planner
        else None
    )

    store = _session_store()
    sid = session_id or session_id_for_dir(working_dir)
    store.create_session(sid, {"working_dir": working_dir})

    if context is None:
        context = _get_or_create_context(sid, store)

    skills = discover_skills(working_dir, disabled=cfg.get("disabled_skills"))
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

    from likecodex_engine.agent.goal import GoalState

    goal_state = GoalState(max_continuations=int(cfg.get("goal_max_continuations", 20)))

    loop = AgentLoop(
        llm,
        tools,
        context,
        max_iterations=int(cfg.get("max_steps", 0)),
        planner=planner,
        permission_evaluator=evaluator,
        sandbox_executor_url=cfg.get("sandbox_executor_url"),
        memory=memory,
        session_id=sid,
        on_event=on_event,
        agent_factory=agent_factory,
        no_tools=no_tools,
        plan_state=PlanState(),
        goal_state=goal_state,
    )
    loop_holder["loop"] = loop
    tools.set_agent_factory(agent_factory)
    tools.set_session_log_provider(lambda: loop.context.messages)
    tools.set_session_id(sid)

    # Register DeepSeek-specific tools when using DeepSeek provider
    global _DEEPSEEK_TOOLS_REGISTERED
    provider = cfg.get("provider", "deepseek")
    if provider == "deepseek" and not _DEEPSEEK_TOOLS_REGISTERED:
        from likecodex_engine.tools.deepseek_tools import TOOL_DEFINITIONS

        for tool_name, tool_def in TOOL_DEFINITIONS.items():
            tools.register(
                tool_name,
                {
                    "description": tool_def["description"],
                    "parameters": tool_def["parameters"],
                },
                tool_def["handler"],
                read_only=tool_def.get("read_only", True),
            )
        _DEEPSEEK_TOOLS_REGISTERED = True
        _set_current_deepseek_session(loop, context, sid)

    # Inject project_checks from LIKECODEX.md / AGENTS.md
    host_checks = load_host_checks_from_dir(Path(working_dir))
    if host_checks:
        loop.project_checks = [
            {"command": check.command, "source_path": check.source_path, "line": check.line} for check in host_checks
        ]

    _ACTIVE_LOOPS[sid] = loop
    if enable_planner and planner_llm is not None:
        planning_context = context.prefix.project_memories if hasattr(context, "prefix") else ""

        # Create classifier LLM if auto_plan_classifier is configured
        classifier_llm = None
        auto_plan_classifier_model = cfg.get("auto_plan_classifier")
        if auto_plan_classifier_model:
            classifier_llm = create_provider(
                cfg.get("provider", "deepseek"),
                auto_plan_classifier_model,
                cfg.get("api_key"),
                cfg.get("base_url"),
                thinking=False,
            )

        coordinator = Coordinator(
            loop,
            planner_llm,
            planner_max_steps=int(cfg.get("planner_max_steps", 20)),
            planning_context=planning_context,
            auto_plan=cfg.get("auto_plan", "off"),
            auto_plan_classifier=classifier_llm,
        )
        _ACTIVE_COORDINATORS[sid] = coordinator
    return loop


async def _ensure_mcp(config: dict, tools: ToolRegistry) -> None:
    if str(config.get("enable_mcp", "false")).lower() not in ("1", "true", "yes"):
        return
    if str(config.get("token_mode", "full")).lower() == "economy":
        return
    startup = str(config.get("mcp_startup", "lazy")).lower()
    await register_mcp_tools(tools, config, eager_only=(startup == "lazy"))


async def chat(request: web.Request) -> web.StreamResponse:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    no_tools = bool(data.get("no_tools", False))
    cfg = _resolve_config(request.app[APP_CONFIG])
    cfg = _merge_request_config(cfg, data)
    working_dir = cfg.get("working_dir", ".")

    sid = session_id or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context, no_tools=no_tools)
    await _ensure_mcp(cfg, loop.tools)
    store.append_event(sid, SessionEvent(event_type="user", content=prompt, metadata={}))
    _set_current_deepseek_session(loop, context, sid)

    runner = _get_runner(sid)
    prepared = prepare_turn(
        sid=sid,
        prompt=prompt,
        working_dir=working_dir,
        context=context,
        runner=runner,
        loop=loop,
    )

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

    # Keep-alive heartbeat to prevent proxy timeouts
    keepalive_stop = asyncio.Event()

    async def _keepalive() -> None:
        try:
            while not keepalive_stop.is_set():
                await asyncio.wait_for(keepalive_stop.wait(), timeout=15)
                if keepalive_stop.is_set():
                    break
                await response.write(b": keepalive\n\n")
        except TimeoutError:
            if not keepalive_stop.is_set():
                await response.write(b": keepalive\n\n")
        except Exception:
            pass

    keepalive_handle = asyncio.ensure_future(_keepalive())

    try:
        if prepared.expanded.compact_trigger:
            async for resp in _run_manual_compact(context, loop.llm, prepared.expanded.compact_focus):
                payload = json.dumps(_serialize_response(resp))
                await response.write(f"data: {payload}\n\n".encode())
            await response.write(b"data: [DONE]\n\n")
            return response

        for resp in prepared.early_responses:
            payload = json.dumps(_serialize_response(resp))
            await response.write(f"data: {payload}\n\n".encode())

        if prepared.expanded.direct_reply is not None:
            await response.write(b"data: [DONE]\n\n")
            return response

        async for resp in runner.run(prepared.prompt):
            payload = json.dumps(_serialize_response(resp))
            await response.write(f"data: {payload}\n\n".encode())
        cache_stats = global_cache_metrics().to_dict()
        cache_event = json.dumps({"type": "cache_stats", "content": "", "cache": cache_stats})
        await response.write(f"data: {cache_event}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
    finally:
        keepalive_stop.set()
        keepalive_handle.done() or keepalive_handle.cancel()

    return response


async def run_task(request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    cfg = _resolve_config(request.app[APP_CONFIG])
    cfg = _merge_request_config(cfg, data)
    working_dir = cfg.get("working_dir", ".")

    sid = session_id or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context)
    await _ensure_mcp(cfg, loop.tools)
    store.append_event(sid, SessionEvent(event_type="user", content=prompt, metadata={}))
    _set_current_deepseek_session(loop, context, sid)

    runner = _get_runner(sid)
    prepared = prepare_turn(
        sid=sid,
        prompt=prompt,
        working_dir=working_dir,
        context=context,
        runner=runner,
        loop=loop,
    )

    outputs = [_serialize_response(r) for r in prepared.early_responses]

    if prepared.expanded.compact_trigger:
        async for resp in _run_manual_compact(context, loop.llm, prepared.expanded.compact_focus):
            outputs.append(_serialize_response(resp))
        return web.json_response({"outputs": outputs, "session_id": sid})

    if prepared.expanded.direct_reply is not None:
        return web.json_response({"outputs": outputs, "session_id": sid})

    async for resp in runner.run(prepared.prompt):
        outputs.append(_serialize_response(resp))

    return web.json_response({"outputs": outputs, "session_id": sid, "cache": global_cache_metrics().to_dict()})


async def plan_task(request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    cfg = _resolve_config(request.app[APP_CONFIG])

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
    cfg = _resolve_config(request.app[APP_CONFIG])
    cfg = _merge_request_config(cfg, data)
    working_dir = cfg.get("working_dir", ".")
    task_id = session_id or session_id_for_dir(working_dir)

    store = _session_store()
    store.create_session(task_id, {"prompt": prompt, "status": "running"})

    async def run_in_background() -> None:
        context = _get_or_create_context(task_id, store)
        loop = _make_agent(cfg, session_id=task_id, context=context)
        await _ensure_mcp(cfg, loop.tools)
        store.append_event(task_id, SessionEvent(event_type="user", content=prompt, metadata={}))
        try:
            runner = _get_runner(task_id)
            prepared = prepare_turn(
                sid=task_id,
                prompt=prompt,
                working_dir=working_dir,
                context=context,
                runner=runner,
                loop=loop,
            )
            for resp in prepared.early_responses:
                metadata = {"model": resp.model, **(resp.metadata or {})}
                store.append_event(
                    task_id,
                    SessionEvent(event_type=resp.event_type, content=resp.content, metadata=metadata),
                )
            if prepared.expanded.compact_trigger:
                async for resp in _run_manual_compact(context, loop.llm, prepared.expanded.compact_focus):
                    metadata = {"model": resp.model, **(resp.metadata or {})}
                    store.append_event(
                        task_id,
                        SessionEvent(event_type=resp.event_type, content=resp.content, metadata=metadata),
                    )
                store.create_session(task_id, {"prompt": prompt, "status": "completed"})
                return
            if prepared.expanded.direct_reply is not None:
                store.create_session(task_id, {"prompt": prompt, "status": "completed"})
                return
            async for resp in runner.run(prepared.prompt):
                metadata = {"model": resp.model}
                if resp.usage:
                    metadata["usage"] = resp.usage
                if resp.metadata:
                    metadata.update(resp.metadata)
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
            _ACTIVE_COORDINATORS.pop(task_id, None)

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
    grant_scope = str(data.get("grant_scope", "once"))
    for sid in list(_ACTIVE_LOOPS.keys()) + list(_ACTIVE_COORDINATORS.keys()):
        runner = _get_runner(sid)
        if await runner.respond_permission(request_id, approved, grant_scope=grant_scope):
            return web.json_response({"ok": True, "request_id": request_id, "approved": approved})
    return web.json_response({"error": "Permission request not found"}, status=404)


async def list_pending_asks(request: web.Request) -> web.Response:
    pending: list[dict] = []
    seen: set[str] = set()
    for sid in set(_ACTIVE_LOOPS) | set(_ACTIVE_COORDINATORS):
        loop = _resolve_loop(sid)
        if loop is None:
            continue
        for item in loop.list_pending_asks():
            rid = item.get("request_id")
            if rid and rid not in seen:
                seen.add(rid)
                pending.append(item)
    return web.json_response({"pending": pending})


async def respond_ask(request: web.Request) -> web.Response:
    request_id = request.match_info["id"]
    data = await request.json()
    answers = data.get("answers", [])
    for sid in list(_ACTIVE_LOOPS.keys()) + list(_ACTIVE_COORDINATORS.keys()):
        loop = _resolve_loop(sid)
        if loop and await loop.respond_ask(request_id, answers):
            return web.json_response({"ok": True, "request_id": request_id})
    return web.json_response({"error": "Ask request not found"}, status=404)


async def list_checkpoints(request: web.Request) -> web.Response:
    cfg = _resolve_config(request.app[APP_CONFIG])
    manager = CheckpointManager(cfg.get("working_dir", "."))
    return web.json_response({"checkpoints": [c.to_dict() for c in manager.list_checkpoints()]})


async def codegraph_search(request: web.Request) -> web.Response:
    pattern = request.query.get("pattern", "")
    cfg = _resolve_config(request.app[APP_CONFIG])
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
    return web.json_response({"pattern": pattern, "results": results, "files": graph.file_count})


async def rewind_checkpoint(request: web.Request) -> web.Response:
    data = await request.json()
    checkpoint_id = data.get("checkpoint_id")
    mode = data.get("mode", "code")
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    session_id = data.get("session_id") or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(session_id, store)
    from likecodex_engine.agent.rewind import RewindController

    controller = RewindController(working_dir, context, session_id, store)
    result = controller.rewind(checkpoint_id, mode=mode)
    status = 200 if result.get("ok") else 400
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


# ── New ACP-compatible handler functions ───────────────────────────


async def toggle_plan_mode(request: web.Request) -> web.Response:
    """Toggle plan mode for a session."""
    data = await request.json()
    session_id = data.get("session_id", "")
    loop = _resolve_loop(session_id)
    if loop is None:
        return web.json_response({"error": "Session not found"}, status=404)
    if hasattr(loop, "plan_state"):
        loop.plan_state.active = not loop.plan_state.active
        return web.json_response(
            {
                "ok": True,
                "active": loop.plan_state.active,
                "session_id": session_id,
            }
        )
    return web.json_response({"error": "Plan mode not supported"}, status=400)


async def compact_context(request: web.Request) -> web.Response:
    """Trigger context compaction for a session."""
    data = await request.json()
    session_id = data.get("session_id", "")
    focus = data.get("focus")
    loop = _resolve_loop(session_id)
    if loop is None:
        return web.json_response({"error": "Session not found"}, status=404)
    # Trigger compaction via the agent's context manager
    if hasattr(loop, "context") and hasattr(loop.context, "compact"):
        loop.context.compact(trigger="manual", focus=focus)
        return web.json_response({"ok": True, "session_id": session_id})
    return web.json_response({"error": "Compaction not supported"}, status=400)


async def new_session(request: web.Request) -> web.Response:
    """Create a new empty session."""
    data = await request.json()
    cwd = data.get("cwd", ".")
    session_id = str(uuid.uuid4())
    store = _session_store()
    store.create_session(session_id, {"working_dir": cwd, "status": "active"})
    _CONTEXT_CACHE.pop(session_id)
    return web.json_response({"ok": True, "session_id": session_id, "cwd": cwd})


async def fork_session(request: web.Request) -> web.Response:
    """Fork a session at the current point."""
    data = await request.json()
    session_id = data.get("session_id", "")
    label = data.get("label", "fork")
    store = _session_store()
    new_id = str(uuid.uuid4())
    events = store.list_events(session_id)
    if not events:
        return web.json_response({"error": "Source session not found"}, status=404)
    store.create_session(
        new_id,
        {
            "working_dir": ".",
            "status": "active",
            "forked_from": session_id,
            "label": label,
        },
    )
    for e in events:
        store.append_event(new_id, e)
    return web.json_response({"ok": True, "session_id": new_id, "forked_from": session_id})


async def summarize_session(request: web.Request) -> web.Response:
    """Generate a summary of a session."""
    data = await request.json()
    session_id = data.get("session_id", "")
    store = _session_store()
    events = store.list_events(session_id)
    if not events:
        return web.json_response({"error": "Session not found"}, status=404)
    user_messages = [e.content for e in events if e.event_type == "user"]
    assistant_messages = [e.content for e in events if e.event_type == "assistant"]
    summary = {
        "session_id": session_id,
        "message_count": len(events),
        "user_turns": len(user_messages),
        "assistant_turns": len(assistant_messages),
        "first_user_message": user_messages[0] if user_messages else None,
        "last_assistant_message": assistant_messages[-1] if assistant_messages else None,
    }
    return web.json_response(summary)


async def set_approval_mode(request: web.Request) -> web.Response:
    """Set the tool approval mode for a session."""
    data = await request.json()
    session_id = data.get("session_id", "")
    mode = data.get("mode", "auto")
    loop = _resolve_loop(session_id)
    if loop is None:
        return web.json_response({"error": "Session not found"}, status=404)
    valid_modes = {"read-only", "auto", "auto-approve", "full-access", "yolo", "sandbox-required"}
    if mode not in valid_modes:
        return web.json_response({"error": f"Invalid mode: {mode}. Valid: {sorted(valid_modes)}"}, status=400)
    if hasattr(loop, "permission_evaluator"):
        loop.permission_evaluator.mode = ApprovalMode(mode)
        return web.json_response({"ok": True, "session_id": session_id, "mode": mode})
    return web.json_response({"error": "Approval mode not supported"}, status=400)


async def resume_session(request: web.Request) -> web.Response:
    """Resume a saved session."""
    data = await request.json()
    session_id = data.get("session_id", "")
    store = _session_store()
    events = store.list_events(session_id)
    if not events:
        return web.json_response({"error": "Session not found"}, status=404)
    metadata = store.get_session_metadata(session_id) or {}
    return web.json_response(
        {
            "ok": True,
            "session_id": session_id,
            "event_count": len(events),
            "metadata": metadata,
        }
    )


async def delete_session(request: web.Request) -> web.Response:
    """Delete a session."""
    data = await request.json()
    session_id = data.get("session_id", "")
    store = _session_store()
    metadata = store.get_session_metadata(session_id)
    if not metadata:
        return web.json_response({"error": "Session not found"}, status=404)
    store.delete_session(session_id)
    _CONTEXT_CACHE.pop(session_id)
    _ACTIVE_LOOPS.pop(session_id, None)
    _ACTIVE_COORDINATORS.pop(session_id, None)
    return web.json_response({"ok": True, "session_id": session_id})


async def list_skills(request: web.Request) -> web.Response:
    """List available skills."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    skills = discover_skills(working_dir)
    return web.json_response(
        {"skills": [{"name": s.name, "description": s.description, "source": s.source} for s in skills]}
    )


# ── DeepSeek-specific API handlers ────────────────────────────


async def deepseek_cache_stats(request: web.Request) -> web.Response:
    """Return current DeepSeek prefix cache metrics."""
    metrics = global_cache_metrics()
    from likecodex_engine.context.cache_shape import capture_prefix_shape

    shape = capture_prefix_shape()
    return web.json_response(
        {
            "hit_rate": metrics.hit_rate,
            "recent_hit_rate": metrics.recent_hit_rate,
            "request_count": metrics.request_count,
            "total_hit_tokens": metrics.total_hit_tokens,
            "total_miss_tokens": metrics.total_miss_tokens,
            "prefix_shape": shape,
        }
    )


async def deepseek_api_switch_model(request: web.Request) -> web.Response:
    """Switch the model for an active session via the DeepSeek API."""
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
        return web.json_response(
            {"error": f"Invalid model '{model}'. Valid: {sorted(valid)}"},
            status=400,
        )

    from likecodex_engine.llm.factory import create_provider

    model_map = {"flash": "deepseek-v4-flash", "pro": "deepseek-v4-pro"}
    resolved = model_map.get(model, model)

    old_model = getattr(loop.llm, "model", "unknown")
    loop.llm = create_provider(
        provider="deepseek",
        model=resolved,
    )
    return web.json_response(
        {
            "ok": True,
            "session_id": session_id,
            "switched_from": old_model,
            "switched_to": resolved,
        }
    )


async def deepseek_session_cost(request: web.Request) -> web.Response:
    """Return cumulative cost tracking for the active session."""
    session_id = request.query.get("session_id", "")
    if not session_id:
        cfg = _resolve_config(request.app[APP_CONFIG])
        working_dir = cfg.get("working_dir", ".")
        session_id = session_id_for_dir(working_dir)

    from likecodex_engine.llm.cache_metrics import global_cache_metrics

    metrics = global_cache_metrics()
    from likecodex_engine.llm.deepseek import DeepSeekUsage

    usage = DeepSeekUsage(
        prompt_tokens=metrics.total_hit_tokens + metrics.total_miss_tokens,
        completion_tokens=0,
        cache_hit_tokens=metrics.total_hit_tokens,
        cache_miss_tokens=metrics.total_miss_tokens,
        model="deepseek-v4-flash",
    )
    return web.json_response(
        {
            "session_id": session_id,
            "cache_metrics": {
                "hit_rate": round(metrics.hit_rate, 4),
                "total_requests": metrics.request_count,
            },
            "cost": {
                "input_cost": round(usage.input_cost, 6),
                "output_cost": round(usage.output_cost, 6),
                "total_cost": round(usage.total_cost, 6),
                "currency": "USD",
            },
            "usage": {
                "cache_hit_tokens": metrics.total_hit_tokens,
                "cache_miss_tokens": metrics.total_miss_tokens,
                "cache_hit_rate": round(usage.cache_hit_rate, 4),
                "reasoning_tokens": 0,
            },
        }
    )


async def deepseek_diagnostics(request: web.Request) -> web.Response:
    """Return DeepSeek-specific diagnostics for debugging."""
    session_id = request.query.get("session_id", "")
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    sid = session_id or session_id_for_dir(working_dir)

    store = _session_store()
    context = _get_or_create_context(sid, store)

    from likecodex_engine.context.cache_shape import capture_prefix_shape
    from likecodex_engine.llm.deepseek import DeepSeekProvider

    system_prompt = DeepSeekProvider.load_system_prompt()
    has_custom_prompt = bool(system_prompt)

    shape = {}
    if hasattr(context, "capture_prefix_shape"):
        shape = capture_prefix_shape(
            context.prefix.combined if hasattr(context, "prefix") else "",
            [],
            getattr(context, "rewrite_version", 0),
        )

    return web.json_response(
        {
            "session_id": sid,
            "provider": cfg.get("provider", "deepseek"),
            "system_prompt": {
                "has_custom_deepseek_prompt": has_custom_prompt,
                "length": len(system_prompt) if has_custom_prompt else 0,
                "source": "deepseek_v4_system.txt" if has_custom_prompt else "default",
            },
            "cache": {
                "prefix_stable": shape.get("stable", True) if shape else None,
                "rewrite_version": getattr(context, "rewrite_version", 0),
                "log_size": len(getattr(context, "messages", [])),
            },
            "deepseek_tools_registered": _DEEPSEEK_TOOLS_REGISTERED,
            "config": {
                "api_key_set": bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LIKECODEX_LLM_API_KEY")),
            },
        }
    )


async def warmup_deepseek_cache() -> None:
    """Background warmup: prime DeepSeek prefix cache on startup."""
    from likecodex_engine.llm.deepseek import DeepSeekProvider

    try:
        system_prompt = DeepSeekProvider.load_system_prompt()
        if not system_prompt:
            return
        provider = DeepSeekProvider(
            model="deepseek-v4-flash",
            api_key=os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LIKECODEX_LLM_API_KEY"),
        )
        from likecodex_engine.llm.base import Message, Role

        warmup_msgs = [
            Message(role=Role.SYSTEM, content=system_prompt),
            Message(role=Role.USER, content="."),
        ]
        await provider.complete(warmup_msgs, max_tokens=5)
    except Exception:
        pass  # Warmup is best-effort


def create_app(config: dict | None = None) -> web.Application:
    app = web.Application()
    app[APP_CONFIG] = config or {}

    # Background cache warmup on startup
    async def _startup_warmup(app: web.Application) -> None:
        cfg = _resolve_config(app[APP_CONFIG])
        if cfg.get("provider", "deepseek") == "deepseek":
            asyncio.create_task(warmup_deepseek_cache())

    app.on_startup.append(_startup_warmup)
    app.router.add_get("/health", health)
    app.router.add_get("/metrics", metrics)
    app.router.add_post("/chat", chat)
    app.router.add_post("/run", run_task)
    app.router.add_post("/plan", plan_task)
    app.router.add_post("/tasks", create_task)
    app.router.add_get("/tasks/{task_id}", get_task)
    app.router.add_get("/permissions/pending", list_pending_permissions)
    app.router.add_post("/permissions/{id}/respond", respond_permission)
    app.router.add_get("/ask/pending", list_pending_asks)
    app.router.add_post("/ask/{id}/respond", respond_ask)
    app.router.add_get("/sessions", list_sessions)
    app.router.add_get("/sessions/{id}/events", get_session_events)
    app.router.add_get("/checkpoints", list_checkpoints)
    app.router.add_post("/checkpoints/rewind", rewind_checkpoint)
    app.router.add_get("/codegraph/search", codegraph_search)
    # ── New ACP-compatible endpoints ──────────────────────────
    app.router.add_post("/plan/toggle", toggle_plan_mode)
    app.router.add_post("/compact", compact_context)
    app.router.add_post("/new", new_session)
    app.router.add_post("/fork", fork_session)
    app.router.add_post("/summarize", summarize_session)
    app.router.add_post("/tool-approval-mode", set_approval_mode)
    app.router.add_post("/resume", resume_session)
    app.router.add_post("/sessions/delete", delete_session)
    app.router.add_get("/skills", list_skills)

    # ── DeepSeek-specific API endpoints ──────────────────────
    app.router.add_get("/api/deepseek/cache-stats", deepseek_cache_stats)
    app.router.add_post("/api/deepseek/switch-model", deepseek_api_switch_model)
    app.router.add_get("/api/deepseek/session-cost", deepseek_session_cost)
    app.router.add_get("/api/deepseek/diagnostics", deepseek_diagnostics)

    # ── Web UI static file serving ──────────────────────────
    if STATIC_DIR.exists():
        app.router.add_static("/static/", path=str(STATIC_DIR), name="static")

        async def spa_handler(request: web.Request) -> web.FileResponse:
            return web.FileResponse(STATIC_DIR / "index.html")

        app.router.add_get("/", spa_handler)

        if LITE_HTML.exists():

            async def lite_handler(request: web.Request) -> web.FileResponse:
                return web.FileResponse(LITE_HTML)

            app.router.add_get("/lite", lite_handler)

    return app


def main() -> None:
    host = os.environ.get("LIKECODEX_ENGINE_HOST", "127.0.0.1")
    port = int(os.environ.get("LIKECODEX_ENGINE_PORT", "9090"))
    config = engine_config_from_env()
    app = create_app(config)
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    main()
