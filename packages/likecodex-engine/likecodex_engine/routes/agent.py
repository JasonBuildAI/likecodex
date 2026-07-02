"""Core Agent API route handlers.

Handles: health, metrics, chat, run, plan, tasks, permissions, asks,
checkpoints, codegraph, sessions, plan mode toggle, context compaction.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
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
from likecodex_engine.context.instruction import load_host_checks_from_dir
from likecodex_engine.context.manager import ContextManager, stable_json_dumps, stable_tool_calls_json
from likecodex_engine.context.project_memory import load_project_memory
from likecodex_engine.context.session_resolver import session_id_for_dir
from likecodex_engine.llm.base import LLMResponse, Message, Role
from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.llm.deepseek import DeepSeekProvider
from likecodex_engine.llm.factory import create_provider
from likecodex_engine.mcp.loader import register_mcp_tools
from likecodex_engine.memory.vector import VectorMemory
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.permissions.policy import Policy
from likecodex_engine.persistence.session import SessionEvent, SessionStore
from likecodex_engine.server_turn import prepare_turn, run_manual_compact_responses
from likecodex_engine.skills.loader import discover_skills, skills_prefix_block, inject_dynamic_context
from likecodex_engine.skills.state import is_skill_enabled, set_skill_enabled, load_skill_state
from likecodex_engine.tools.registry import ToolRegistry

from likecodex_engine.config_loader import clear_config_cache
from likecodex_engine.routes._shared import (
    APP_CONFIG,
    _ACTIVE_LOOPS,
    _ACTIVE_COORDINATORS,
    _BACKGROUND_TASKS,
    _CONTEXT_CACHE,
    _SESSION_STORE,
    _DEEPSEEK_TOOLS_REGISTERED,
    _RESOLVED_CONFIG_CACHE,
    _RESOLVED_CONFIG_KEYS,
    _make_sse_response,
    _sse_write,
    _sse_done,
    _SSEKeepalive,
    _set_current_deepseek_session,
    _session_store,
    _resolve_config,
    _cfg_wd,
    _merge_request_config,
    _get_or_create_context,
    _get_runner,
    _resolve_loop,
    _serialize_response,
    _run_manual_compact,
)

logger = logging.getLogger(__name__)


async def health(request: web.Request) -> web.Response:
    """Comprehensive health check endpoint.

    Returns engine status, configuration summary, and cache metrics.
    """
    metrics = global_cache_metrics().to_dict()
    config = request.app.get(APP_CONFIG, {})
    return web.json_response({
        "status": "ok",
        "version": __import__("likecodex_engine").__version__,
        "provider": config.get("provider", "deepseek"),
        "model": config.get("model", "deepseek-v4-flash"),
        "python": sys.version,
        "uptime": time.time() - _ENGINE_START_TIME,
        "cache": metrics,
        "active_sessions": len(_ACTIVE_LOOPS),
        "active_coordinators": len(_ACTIVE_COORDINATORS),
    })


async def liveness(request: web.Request) -> web.Response:
    """Lightweight liveness probe for orchestration systems."""
    return web.json_response({"status": "alive"})


async def readiness(request: web.Request) -> web.Response:
    """Readiness probe - indicates if the engine is ready to accept requests."""
    config = request.app.get(APP_CONFIG, {})
    api_key = config.get("api_key") or os.environ.get("LIKECODEX_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    ready = bool(api_key)
    return web.json_response({
        "status": "ready" if ready else "not_ready",
        "api_key_configured": bool(api_key),
        "model": config.get("model", "unknown"),
    })


_ENGINE_START_TIME = time.time()


async def metrics(request: web.Request) -> web.Response:
    return web.json_response(global_cache_metrics().to_dict())


async def reload_config(request: web.Request) -> web.Response:
    """Hot-reload configuration from files and environment."""
    clear_config_cache()
    _RESOLVED_CONFIG_CACHE.clear()
    from likecodex_engine.config_loader import get_config_with_hot_reload
    new_config = get_config_with_hot_reload(validate=False)
    request.app[APP_CONFIG] = new_config
    return web.json_response({"status": "ok", "message": "Configuration reloaded"})


def _make_agent(
    config: dict,
    enable_planner: bool | None = None,
    session_id: str | None = None,
    context: ContextManager | None = None,
    no_tools: bool = False,
    agent_mode: str = "agent",
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
    if agent_mode == "manual":
        approval_mode = "ask"
    elif agent_mode == "ask":
        approval_mode = "read-only"
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
        agent_mode=agent_mode,
    )
    loop_holder["loop"] = loop
    tools.set_agent_factory(agent_factory)
    tools.set_session_log_provider(lambda: loop.context.messages)
    tools.set_session_id(sid)

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

    host_checks = load_host_checks_from_dir(Path(working_dir))
    if host_checks:
        loop.project_checks = [
            {"command": check.command, "source_path": check.source_path, "line": check.line} for check in host_checks
        ]

    _ACTIVE_LOOPS[sid] = loop
    if enable_planner and planner_llm is not None:
        planning_context = context.prefix.project_memories if hasattr(context, "prefix") else ""

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
    agent_mode = data.get("agent_mode", "agent")
    active_files = data.get("active_files", [])
    no_tools = bool(data.get("no_tools", False))
    if agent_mode == "ask":
        no_tools = True
    cfg = _resolve_config(request.app[APP_CONFIG])
    cfg = _merge_request_config(cfg, data)
    working_dir = cfg.get("working_dir", ".")

    sid = session_id or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context, no_tools=no_tools, agent_mode=agent_mode)
    await _ensure_mcp(cfg, loop.tools)

    if active_files and isinstance(active_files, list):
        context.inject_active_files(active_files, working_dir)

    skill_name = data.get("skill")
    skill_event = None
    if skill_name:
        skills = discover_skills(working_dir)
        skill = next((s for s in skills if s.name == skill_name), None)
        if skill:
            body = inject_dynamic_context(skill.body, skill.source_dir)
            skill_args = data.get("skill_args", "")
            if skill_args:
                body = body.replace("$ARGS", skill_args).replace("$1", skill_args)
            context.add_context_block(f"[Skill: {skill.name}]\n{skill.description}\n\n{body[:8000]}")
            skill_event = {
                "type": "skill_invoked",
                "content": json.dumps({
                    "skill": skill.name,
                    "mode": skill.run_as,
                    "body": body[:2000],
                }),
            }

    if agent_mode in ("ask", "agent", "manual"):
        _mode_prompt_file = Path(__file__).parent.parent / "prompts" / f"{agent_mode}_mode.txt"
        if _mode_prompt_file.exists():
            _mode_prompt = _mode_prompt_file.read_text(encoding="utf-8").strip()
            if _mode_prompt:
                context.add_context_block(f"[Agent Mode: {agent_mode.upper()}]\n{_mode_prompt}")

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

    response = _make_sse_response()
    response.headers["X-Session-Id"] = sid
    await response.prepare(request)

    async with _SSEKeepalive(response):
        try:
            if skill_event:
                await _sse_write(response, json.dumps(skill_event))

            if prepared.expanded.compact_trigger:
                async for resp in _run_manual_compact(context, loop.llm, prepared.expanded.compact_focus):
                    payload = json.dumps(_serialize_response(resp))
                    await _sse_write(response, payload)
                await _sse_done(response)
                return response

            for resp in prepared.early_responses:
                payload = json.dumps(_serialize_response(resp))
                await _sse_write(response, payload)

            if prepared.expanded.direct_reply is not None:
                await _sse_done(response)
                return response

            async for resp in runner.run(prepared.prompt):
                payload = json.dumps(_serialize_response(resp))
                await _sse_write(response, payload)
            cache_stats = global_cache_metrics().to_dict()
            cache_event = json.dumps({"type": "cache_stats", "content": "", "cache": cache_stats})
            await _sse_write(response, cache_event)
            await _sse_done(response)
        except Exception:
            logger.warning("chat SSE stream failed", exc_info=True)

    return response


async def run_task(request: web.Request) -> web.Response:
    data = await request.json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id")
    agent_mode = data.get("agent_mode", "agent")
    active_files = data.get("active_files", [])
    cfg = _resolve_config(request.app[APP_CONFIG])
    cfg = _merge_request_config(cfg, data)
    working_dir = cfg.get("working_dir", ".")

    sid = session_id or session_id_for_dir(working_dir)
    store = _session_store()
    context = _get_or_create_context(sid, store)
    loop = _make_agent(cfg, session_id=sid, context=context, agent_mode=agent_mode)
    await _ensure_mcp(cfg, loop.tools)

    if active_files and isinstance(active_files, list):
        context.inject_active_files(active_files, working_dir)

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

    task = asyncio.create_task(run_in_background())
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

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


async def codegraph_symbols(request: web.Request) -> web.Response:
    path = request.query.get("path", "")
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    from likecodex_engine.tools.codegraph import load_or_build

    graph = load_or_build(working_dir)
    norm = path.replace("\\", "/")
    symbols = [
        {"name": s.name, "kind": s.kind, "line": s.line}
        for s in graph.symbols
        if s.path.replace("\\", "/") == norm
    ]
    symbols.sort(key=lambda s: s["line"])
    return web.json_response({"path": path, "symbols": symbols, "count": len(symbols)})


async def codegraph_callers(request: web.Request) -> web.Response:
    name = request.query.get("name", "")
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    from likecodex_engine.tools.codegraph import load_or_build

    graph = load_or_build(working_dir)
    callers = [
        {
            "path": site.rpartition(":")[0],
            "line": int(site.rpartition(":")[2]) if site.rpartition(":")[2].isdigit() else 0,
        }
        for site in graph.references.get(name, [])[:50]
    ]
    return web.json_response({"symbol": name, "callers": callers, "count": len(callers)})


async def codegraph_viz(request: web.Request) -> web.Response:
    name = request.query.get("name", "")
    max_depth = int(request.query.get("max_depth", "2"))
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    from likecodex_engine.tools.code_search import CodeSearchTools

    search = CodeSearchTools(working_dir)
    result = await search.codegraph_viz(name, max_depth=max_depth)
    return web.json_response(json.loads(result))


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


async def toggle_plan_mode(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    loop = _resolve_loop(session_id)
    if loop is None:
        return web.json_response({"error": "Session not found"}, status=404)
    if hasattr(loop, "plan_state"):
        loop.plan_state.active = not loop.plan_state.active
        return web.json_response({"ok": True, "active": loop.plan_state.active, "session_id": session_id})
    return web.json_response({"error": "Plan mode not supported"}, status=400)


async def set_agent_mode(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    mode = data.get("mode", "agent")
    if mode not in ("agent", "ask", "manual", "plan"):
        return web.json_response({"error": f"Invalid mode: {mode}"}, status=400)
    loop = _resolve_loop(session_id)
    if loop is None:
        return web.json_response({"error": "Session not found"}, status=404)
    old_mode = getattr(loop, "agent_mode", "")
    loop.agent_mode = mode
    store = _session_store()
    store.append_event(
        session_id,
        SessionEvent(
            event_type="mode_changed",
            content=json.dumps({"from": old_mode, "to": mode}),
            metadata={"agent_mode": mode, "from_mode": old_mode, "to_mode": mode},
        ),
    )
    return web.json_response({"ok": True, "session_id": session_id, "mode": mode, "from_mode": old_mode})


async def compact_context(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    focus = data.get("focus")
    loop = _resolve_loop(session_id)
    if loop is None:
        return web.json_response({"error": "Session not found"}, status=404)
    if hasattr(loop, "context") and hasattr(loop.context, "compact_async"):
        result = await loop.context.compact_async(instructions=focus or "", force=True)
        return web.json_response({
            "ok": result.get("compacted", True),
            "session_id": session_id,
            "reason": result.get("reason"),
            "message": result.get("message"),
        })
    return web.json_response({"error": "Compaction not supported"}, status=400)


async def new_session(request: web.Request) -> web.Response:
    data = await request.json()
    cwd = data.get("cwd", ".")
    session_id = str(uuid.uuid4())
    store = _session_store()
    store.create_session(session_id, {"working_dir": cwd, "status": "active"})
    _CONTEXT_CACHE.pop(session_id)
    return web.json_response({"ok": True, "session_id": session_id, "cwd": cwd})


async def fork_session(request: web.Request) -> web.Response:
    data = await request.json()
    session_id = data.get("session_id", "")
    label = data.get("label", "fork")
    store = _session_store()
    new_id = str(uuid.uuid4())
    events = store.list_events(session_id)
    if not events:
        return web.json_response({"error": "Source session not found"}, status=404)
    store.create_session(new_id, {"working_dir": ".", "status": "active", "forked_from": session_id, "label": label})
    for e in events:
        store.append_event(new_id, e)
    return web.json_response({"ok": True, "session_id": new_id, "forked_from": session_id})


async def summarize_session(request: web.Request) -> web.Response:
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
    data = await request.json()
    session_id = data.get("session_id", "")
    store = _session_store()
    events = store.list_events(session_id)
    if not events:
        return web.json_response({"error": "Session not found"}, status=404)
    metadata = store.get_session_metadata(session_id) or {}
    return web.json_response({"ok": True, "session_id": session_id, "event_count": len(events), "metadata": metadata})


async def delete_session(request: web.Request) -> web.Response:
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


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_get("/health", health)
    app.router.add_get("/health/liveness", liveness)
    app.router.add_get("/health/readiness", readiness)
    app.router.add_get("/metrics", metrics)
    app.router.add_post("/admin/reload", reload_config)
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
    app.router.add_get("/codegraph/symbols", codegraph_symbols)
    app.router.add_get("/codegraph/callers", codegraph_callers)
    app.router.add_get("/codegraph/viz", codegraph_viz)
    app.router.add_post("/plan/toggle", toggle_plan_mode)
    app.router.add_post("/compact", compact_context)
    app.router.add_post("/new", new_session)
    app.router.add_post("/fork", fork_session)
    app.router.add_post("/summarize", summarize_session)
    app.router.add_post("/tool-approval-mode", set_approval_mode)
    app.router.add_post("/resume", resume_session)
    app.router.add_post("/sessions/delete", delete_session)
    app.router.add_post("/agent/mode", set_agent_mode)
