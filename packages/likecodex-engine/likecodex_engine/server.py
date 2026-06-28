"""HTTP bridge server exposing the Python agent engine."""

from __future__ import annotations

import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)

# Web UI static files directory
STATIC_DIR = Path(__file__).parent / "static"
LITE_HTML = STATIC_DIR / "lite" / "index.html"

APP_CONFIG = web.AppKey("config", dict)

_ACTIVE_LOOPS: dict[str, AgentLoop] = {}
_ACTIVE_COORDINATORS: dict[str, Coordinator] = {}
# Track background tasks to prevent premature GC (Python < 3.11)
_BACKGROUND_TASKS: set[asyncio.Task] = set()
_SESSION_STORE: SessionStore | None = None
_CONTEXT_CACHE = SessionContextCache()

# Track whether DeepSeek tools have been registered
_DEEPSEEK_TOOLS_REGISTERED: bool = False


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
    # Override approval mode based on agent_mode
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
        agent_mode=agent_mode,
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

    # Inject active files into context if provided
    if active_files and isinstance(active_files, list):
        context.inject_active_files(active_files, working_dir)

    # Inject mode-specific system instructions per turn
    if agent_mode in ("ask", "agent", "manual"):
        _mode_prompt_file = Path(__file__).parent / "prompts" / f"{agent_mode}_mode.txt"
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

    # Inject active files into context if provided
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


# ── Inline Edit API (for AI inline code editing) ──────────────


INLINE_EDIT_SYSTEM = """You are an expert code editor. Your task is to modify the given code according to the user's instruction.
Output ONLY the modified code, wrapped in ```<language> code ``` markers. Do NOT include explanations or commentary — just the code block."""

INLINE_EDIT_USER = """Language: {language}

{context_section}---

## Code to modify:
```{language}
{code}
```

## Instruction:
{instruction}

## Modified code:"""


async def inline_edit(request: web.Request) -> web.Response:
    """AI-powered inline code editing (Cursor-like Ctrl+K)."""
    data = await request.json()
    code: str = data.get("code", "")
    instruction: str = data.get("instruction", "")
    language: str = data.get("language", "plaintext")
    full_content: str | None = data.get("full_content")
    file_path: str | None = data.get("file_path")

    if not code or not instruction:
        return web.json_response({"error": "code and instruction are required"}, status=400)

    cfg = _resolve_config(request.app[APP_CONFIG])
    try:
        llm = create_provider(
            provider=cfg.get("provider", "deepseek"),
            model=data.get("model") or cfg.get("model", "deepseek-v4-flash"),
            api_key=data.get("api_key") or cfg.get("api_key"),
            base_url=cfg.get("base_url"),
        )
    except Exception as e:
        return web.json_response({"error": f"Failed to create LLM provider: {e}"}, status=500)

    context_section = ""
    if full_content:
        import textwrap
        snippet = textwrap.dedent(full_content)
        context_section = f"## Full file context ({language}):\n```{language}\n{snippet}\n```\n\n"

    from likecodex_engine.llm.base import Message, Role

    messages = [
        Message(role=Role.SYSTEM, content=INLINE_EDIT_SYSTEM),
        Message(
            role=Role.USER,
            content=INLINE_EDIT_USER.format(
                language=language,
                context_section=context_section,
                code=code,
                instruction=instruction,
            ),
        ),
    ]

    try:
        response = await llm.complete(messages, temperature=0.1, max_tokens=4096)
    except Exception as e:
        return web.json_response({"error": f"LLM call failed: {e}"}, status=502)

    raw = response.content.strip()

    # Extract code from markdown code block
    import re
    modified = raw
    code_block_match = re.search(r"```(?:\w+)?\n(.*?)\n```", raw, re.DOTALL)
    if code_block_match:
        modified = code_block_match.group(1).strip()

    return web.json_response({
        "original": code,
        "modified": modified,
        "explanation": "",
        "model": response.model,
        "usage": response.usage,
    })


# ── Workspace API (for IDE file tree & editor) ────────────────────


async def workspace_list(request: web.Request) -> web.Response:
    """List files and directories in the workspace."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = Path(cfg.get("working_dir", "."))
    rel_path = request.query.get("path", ".")
    depth_str = request.query.get("depth", "1")

    try:
        depth = int(depth_str)
    except ValueError:
        depth = 1

    target = (working_dir / rel_path).resolve()
    # Security: ensure target is within working_dir
    if not str(target).startswith(str(working_dir.resolve())):
        return web.json_response({"error": "Path outside workspace"}, status=403)
    if not target.exists():
        return web.json_response({"error": "Path not found"}, status=404)

    result: dict = {"name": target.name, "path": str(target.relative_to(working_dir)), "type": "directory" if target.is_dir() else "file"}

    if target.is_dir():
        children = []
        try:
            for entry in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Skip hidden files/dirs (starting with .)
                if entry.name.startswith(".") and entry.name not in (".gitignore", ".env.example", ".editorconfig"):
                    continue
                # Skip node_modules, target, __pycache__
                if entry.name in ("node_modules", "target", "__pycache__", ".git", ".next", "out"):
                    continue
                child = {
                    "name": entry.name,
                    "path": str(entry.relative_to(working_dir)),
                    "type": "directory" if entry.is_dir() else "file",
                }
                if entry.is_file():
                    try:
                        stat = entry.stat()
                        child["size"] = stat.st_size
                    except OSError:
                        child["size"] = 0
                children.append(child)
                if len(children) >= 500:
                    break
        except PermissionError:
            pass
        result["children"] = children

    return web.json_response(result)


async def workspace_read(request: web.Request) -> web.Response:
    """Read a file from the workspace."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = Path(cfg.get("working_dir", "."))
    rel_path = request.query.get("path", "")

    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)

    target = (working_dir / rel_path).resolve()
    if not str(target).startswith(str(working_dir.resolve())):
        return web.json_response({"error": "Path outside workspace"}, status=403)
    if not target.exists() or not target.is_file():
        return web.json_response({"error": "File not found"}, status=404)

    try:
        size_limit = 1024 * 1024  # 1MB
        if target.stat().st_size > size_limit:
            return web.json_response({"error": "File too large"}, status=413)
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return web.json_response({"error": f"Cannot read file: {e}"}, status=500)

    return web.json_response({
        "path": rel_path,
        "name": target.name,
        "content": content,
        "size": target.stat().st_size,
    })


async def workspace_write(request: web.Request) -> web.Response:
    """Write content to a file in the workspace."""
    data = await request.json()
    rel_path = data.get("path", "")
    content = data.get("content", "")

    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)

    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = Path(cfg.get("working_dir", "."))
    target = (working_dir / rel_path).resolve()

    if not str(target).startswith(str(working_dir.resolve())):
        return web.json_response({"error": "Path outside workspace"}, status=403)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        return web.json_response({"error": f"Cannot write file: {e}"}, status=500)

    return web.json_response({"ok": True, "path": rel_path, "size": target.stat().st_size})


# ── IDE Completion API (Tab completion) ────────────────────────

# Lazy-initialized completion service
_completion_service: "InlineCompletionService | None" = None


def _get_completion_service():
    global _completion_service
    if _completion_service is None:
        from likecodex_engine.completion.inline import InlineCompletionService
        _completion_service = InlineCompletionService()
    return _completion_service


async def ide_inline_completion(request: web.Request) -> web.Response:
    """Provide AI-powered inline code completion for the IDE."""
    data = await request.json()

    file_path = data.get("file_path", "")
    language = data.get("language", "plaintext")
    prefix = data.get("prefix", "")
    suffix = data.get("suffix", "")
    imports = data.get("imports", [])
    current_scope = data.get("current_scope", "")
    cursor_line = data.get("cursor_line", 0)
    cursor_col = data.get("cursor_col", 0)

    if not prefix:
        return web.json_response({"text": None})

    cfg = _resolve_config(request.app[APP_CONFIG])
    try:
        llm = create_provider(
            provider=cfg.get("provider", "deepseek"),
            model=cfg.get("model", "deepseek-v4-flash"),
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
        )
    except Exception as e:
        return web.json_response(
            {"error": f"Failed to create LLM provider: {e}"}, status=500
        )

    from likecodex_engine.completion.inline import InlineCompletionRequest

    req = InlineCompletionRequest(
        file_path=file_path,
        language=language,
        prefix=prefix[-2000:],  # limit prefix to 2000 chars
        suffix=suffix[:500],   # limit suffix to 500 chars
        imports=imports if isinstance(imports, list) else [],
        current_scope=current_scope,
        cursor_line=cursor_line,
        cursor_col=cursor_col,
    )

    service = _get_completion_service()
    result = await service.complete(req, llm=llm)

    if result:
        return web.json_response({
            "text": result.text,
            "completion_id": result.completion_id,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "cache_hit": result.cache_hit,
        })

    return web.json_response({"text": None})


async def ide_completion_accepted(request: web.Request) -> web.Response:
    """Track completion acceptance (for future optimization)."""
    return web.json_response({"ok": True})


# ── IDE Context Search API (@ mentions) ────────────────────────

async def ide_context_search(request: web.Request) -> web.Response:
    """Search for @ mention targets (files, symbols, special context)."""
    query = request.query.get("q", "")
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = Path(cfg.get("working_dir", "."))

    from likecodex_engine.context.mention_search import MentionSearchService

    service = MentionSearchService(working_dir)
    results = await service.search(query, limit=20)

    return web.json_response({"results": results})


# ── IDE LSP API (definition, references, hover) ───────────────

# Lazy-initialized LSP manager
_lsp_manager: Any = None


def _get_lsp_manager(working_dir: str):
    global _lsp_manager
    if _lsp_manager is None:
        from likecodex_engine.lsp.manager import LspManager
        _lsp_manager = LspManager(working_dir)
    return _lsp_manager


async def ide_lsp_definition(request: web.Request) -> web.Response:
    """Get definition location for a symbol."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    file_path = data.get("file_path", "")
    line = data.get("line", 1)
    symbol = data.get("symbol", "")

    if not file_path or not symbol:
        return web.json_response({"error": "file_path and symbol are required"}, status=400)

    manager = _get_lsp_manager(working_dir)
    result = await manager.definition(file_path, line, symbol)
    return web.json_response(json.loads(result) if isinstance(result, str) else {"result": result})


async def ide_lsp_references(request: web.Request) -> web.Response:
    """Get references for a symbol."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    file_path = data.get("file_path", "")
    line = data.get("line", 1)
    symbol = data.get("symbol", "")

    if not file_path or not symbol:
        return web.json_response({"error": "file_path and symbol are required"}, status=400)

    manager = _get_lsp_manager(working_dir)
    result = await manager.references(file_path, line, symbol)
    return web.json_response(json.loads(result) if isinstance(result, str) else {"result": result})


async def ide_lsp_hover(request: web.Request) -> web.Response:
    """Get hover info for a symbol."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    file_path = data.get("file_path", "")
    line = data.get("line", 1)
    symbol = data.get("symbol", "")

    if not file_path or not symbol:
        return web.json_response({"error": "file_path and symbol are required"}, status=400)

    manager = _get_lsp_manager(working_dir)
    result = await manager.hover(file_path, line, symbol)
    return web.json_response(json.loads(result) if isinstance(result, str) else {"result": result})


async def ide_lsp_diagnostics(request: web.Request) -> web.Response:
    """Get diagnostics for a file (placeholder — uses LSP server diagnostics)."""
    return web.json_response({"diagnostics": []})


async def ide_composer_chat(request: web.Request) -> web.StreamResponse:
    """Composer SSE endpoint — multi-file AI editing with file change events."""
    data = await request.json()
    message = data.get("message", "")
    mentions = data.get("mentions", [])
    session_id = data.get("sessionId", f"composer-{uuid.uuid4()}")

    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")

    from likecodex_engine.composer.agent import ComposerAgent

    agent = ComposerAgent(config=cfg, working_dir=working_dir)

    response = _make_sse_response()
    await response.prepare(request)

    async with _SSEKeepalive(response):
        try:
            async for event in agent.execute(
                message=message,
                mentions=mentions,
                session_id=session_id,
            ):
                payload = json.dumps(event)
                await response.write(f"data: {payload}\n\n".encode())
        except Exception as exc:
            error_event = json.dumps({"type": "error", "content": str(exc)})
            await response.write(f"data: {error_event}\n\n".encode())

    await response.write(b"data: [DONE]\n\n")
    return response


# ── Git API handlers ───────────────────────────────────────────

_git_service: Any = None


def _get_git_service(working_dir: str):
    """Lazy-load GitService."""
    global _git_service
    if _git_service is None:
        from likecodex_engine.git_service import GitService
        _git_service = GitService(working_dir)
    return _git_service


async def ide_git_status(request: web.Request) -> web.Response:
    """Get git status for the workspace."""
    _, wd = _cfg_wd(request)
    service = _get_git_service(wd)
    result = await service.get_status()
    return web.json_response(result)


async def ide_git_diff(request: web.Request) -> web.Response:
    """Get diff for a specific file."""
    _, wd = _cfg_wd(request)
    service = _get_git_service(wd)
    data = await request.json()
    result = await service.get_diff(
        path=data.get("path", ""),
        staged=data.get("staged", False),
    )
    return web.json_response(result)


async def ide_git_stage(request: web.Request) -> web.Response:
    """Stage a file."""
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).stage_file(data.get("path", ""))
    return web.json_response(result)


async def ide_git_unstage(request: web.Request) -> web.Response:
    """Unstage a file."""
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).unstage_file(data.get("path", ""))
    return web.json_response(result)


async def ide_git_stage_all(request: web.Request) -> web.Response:
    """Stage all changes."""
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).stage_all()
    return web.json_response(result)


async def ide_git_commit(request: web.Request) -> web.Response:
    """Commit staged changes."""
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).commit(
        message=data.get("message", ""),
        author=data.get("author", ""),
        email=data.get("email", ""),
    )
    return web.json_response(result)


async def ide_git_log(request: web.Request) -> web.Response:
    """Get commit log."""
    _, wd = _cfg_wd(request)
    count = int(request.query.get("count", "50"))
    result = await _get_git_service(wd).get_log(count=count)
    return web.json_response(result)


async def ide_git_branches(request: web.Request) -> web.Response:
    """Get all branches."""
    _, wd = _cfg_wd(request)
    result = await _get_git_service(wd).get_branches()
    return web.json_response(result)


async def ide_git_checkout(request: web.Request) -> web.Response:
    """Checkout a branch."""
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).checkout_branch(data.get("name", ""))
    return web.json_response(result)


async def ide_git_create_branch(request: web.Request) -> web.Response:
    """Create a new branch."""
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).create_branch(data.get("name", ""))
    return web.json_response(result)


async def ide_git_discard(request: web.Request) -> web.Response:
    """Discard changes to a file."""
    _, wd = _cfg_wd(request)
    data = await request.json()
    result = await _get_git_service(wd).discard_changes(data.get("path", ""))
    return web.json_response(result)


async def ide_git_search(request: web.Request) -> web.Response:
    """Search file contents."""
    _, wd = _cfg_wd(request)
    query = request.query.get("q", "")
    file_pattern = request.query.get("pattern", "")
    result = await _get_git_service(wd).search_files(query=query, file_pattern=file_pattern)
    return web.json_response(result)


# ── Terminal API handlers ───────────────────────────────────────

_terminal_manager: Any = None


def _get_terminal_manager(working_dir: str):
    """Lazy-load TerminalManager."""
    global _terminal_manager
    if _terminal_manager is None:
        from likecodex_engine.terminal.pty_manager import TerminalManager
        _terminal_manager = TerminalManager(working_dir)
    return _terminal_manager


async def ide_terminal_create(request: web.Request) -> web.Response:
    """Create a new terminal session."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    manager = _get_terminal_manager(working_dir)
    data = await request.json()
    session_id = data.get("id") or f"term-{uuid.uuid4()}"
    cwd = data.get("cwd", working_dir)
    session = manager.create_session(session_id, cwd=cwd)
    return web.json_response({"id": session.id, "cwd": session.cwd, "shell": session.shell})


async def ide_terminal_execute(request: web.Request) -> web.Response:
    """Execute a command and return output (non-streaming)."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    manager = _get_terminal_manager(working_dir)
    data = await request.json()
    session_id = data.get("sessionId", "term-default")
    command = data.get("command", "")
    result = await manager.execute_command(session_id, command)
    return web.json_response(result)


async def ide_terminal_stream(request: web.Request) -> web.StreamResponse:
    """Execute a command with streaming output via SSE."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    manager = _get_terminal_manager(working_dir)
    data = await request.json()
    session_id = data.get("sessionId", "term-default")
    command = data.get("command", "")

    response = _make_sse_response()
    await response.prepare(request)

    try:
        async for event in manager.execute_command_stream(session_id, command):
            payload = json.dumps(event)
            await response.write(f"data: {payload}\n\n".encode())
    except Exception as exc:
        error_event = json.dumps({"type": "error", "content": str(exc)})
        await response.write(f"data: {error_event}\n\n".encode())

    await response.write(b"data: [DONE]\n\n")
    return response


async def ide_terminal_suggest(request: web.Request) -> web.Response:
    """AI command suggestion — natural language to shell command."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    data = await request.json()
    description = data.get("description", "")

    if not description:
        return web.json_response({"command": "", "error": "Description required"}, status=400)

    from likecodex_engine.llm.factory import create_provider
    from likecodex_engine.terminal.ai_assistant import TerminalAIAssistant

    llm = create_provider(
        cfg.get("provider", "deepseek"),
        cfg.get("model", "deepseek-v4-flash"),
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=False,
    )
    assistant = TerminalAIAssistant(llm)
    command = await assistant.suggest_command(description)
    return web.json_response({"command": command})


async def ide_terminal_diagnose(request: web.Request) -> web.Response:
    """AI error diagnosis for terminal commands."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    data = await request.json()
    command = data.get("command", "")
    error_output = data.get("error", "")

    from likecodex_engine.llm.factory import create_provider
    from likecodex_engine.terminal.ai_assistant import TerminalAIAssistant

    llm = create_provider(
        cfg.get("provider", "deepseek"),
        cfg.get("model", "deepseek-v4-flash"),
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=False,
    )
    assistant = TerminalAIAssistant(llm)
    diagnosis = await assistant.diagnose_error(command, error_output)
    return web.json_response({"diagnosis": diagnosis})


async def ide_terminal_close(request: web.Request) -> web.Response:
    """Close a terminal session."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    manager = _get_terminal_manager(working_dir)
    data = await request.json()
    session_id = data.get("sessionId", "")
    success = manager.close_session(session_id)
    return web.json_response({"success": success})


# ── Debug / Test API handlers ───────────────────────────────────

_test_runner: Any = None


def _get_test_runner(working_dir: str):
    """Lazy-load TestRunnerService."""
    global _test_runner
    if _test_runner is None:
        from likecodex_engine.debug.test_runner import TestRunnerService
        _test_runner = TestRunnerService(working_dir)
    return _test_runner


async def ide_tests_discover(request: web.Request) -> web.Response:
    """Discover all test files and test cases."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    runner = _get_test_runner(working_dir)
    result = await runner.discover_tests()
    return web.json_response(result)


async def ide_tests_run(request: web.Request) -> web.StreamResponse:
    """Run tests with SSE streaming."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    runner = _get_test_runner(working_dir)
    data = await request.json()
    test_filter = data.get("filter", "")

    response = _make_sse_response()
    await response.prepare(request)

    try:
        async for event in runner.run_tests(test_filter=test_filter):
            payload = json.dumps(event)
            await response.write(f"data: {payload}\n\n".encode())
    except Exception as exc:
        error_event = json.dumps({"type": "error", "content": str(exc)})
        await response.write(f"data: {error_event}\n\n".encode())

    await response.write(b"data: [DONE]\n\n")
    return response


async def ide_debug_analyze(request: web.Request) -> web.Response:
    """AI error analysis for debugging."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    data = await request.json()
    error_message = data.get("errorMessage", "")
    stack_trace = data.get("stackTrace", "")
    relevant_code = data.get("relevantCode", "")
    file_path = data.get("filePath", "")

    from likecodex_engine.llm.factory import create_provider
    from likecodex_engine.debug.ai_debug import AIDebugAssistant

    llm = create_provider(
        cfg.get("provider", "deepseek"),
        cfg.get("model", "deepseek-v4-flash"),
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=False,
    )
    assistant = AIDebugAssistant(llm)
    result = await assistant.analyze_error(
        error_message=error_message,
        stack_trace=stack_trace,
        relevant_code=relevant_code,
        file_path=file_path,
    )
    return web.json_response(result)


# ── Settings API handlers ────────────────────────────────────────

_settings_manager: Any = None


def _get_settings_manager(working_dir: str):
    """Lazy-load SettingsManager."""
    global _settings_manager
    if _settings_manager is None:
        from likecodex_engine.settings.manager import SettingsManager
        _settings_manager = SettingsManager(working_dir)
    return _settings_manager


async def ide_settings_get_all(request: web.Request) -> web.Response:
    """Get all IDE settings with defaults applied."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    return web.json_response({"settings": mgr.get_all()})


async def ide_settings_categories(request: web.Request) -> web.Response:
    """Get settings grouped by category."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    return web.json_response({"categories": mgr.get_categories()})


async def ide_settings_set(request: web.Request) -> web.Response:
    """Set a single setting value."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    data = await request.json()
    key = data.get("key", "")
    value = data.get("value")
    mgr.set(key, value)
    return web.json_response({"success": True, "key": key, "value": mgr.get(key)})


async def ide_settings_reset(request: web.Request) -> web.Response:
    """Reset a setting to its default value."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    data = await request.json()
    key = data.get("key", "")
    mgr.reset(key)
    return web.json_response({"success": True, "key": key, "value": mgr.get(key)})


async def ide_settings_reset_all(request: web.Request) -> web.Response:
    """Reset all settings to defaults."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    mgr.reset_all()
    return web.json_response({"success": True, "settings": mgr.get_all()})


async def ide_keybindings_get(request: web.Request) -> web.Response:
    """Get all keybindings with conflict info."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    return web.json_response({
        "keybindings": mgr.get_keybindings(),
        "conflicts": mgr.check_conflicts(),
    })


async def ide_keybindings_set(request: web.Request) -> web.Response:
    """Update a keybinding."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    data = await request.json()
    binding_id = data.get("id", "")
    keys = data.get("keys", [])
    mgr.set_keybinding(binding_id, keys)
    return web.json_response({
        "success": True,
        "conflicts": mgr.check_conflicts(),
    })


async def ide_keybindings_reset(request: web.Request) -> web.Response:
    """Reset all keybindings to defaults."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    mgr = _get_settings_manager(working_dir)
    mgr.reset_keybindings()
    return web.json_response({
        "keybindings": mgr.get_keybindings(),
        "conflicts": mgr.check_conflicts(),
    })


# ── Extensions API handlers ──────────────────────────────────────

async def ide_extensions_list(request: web.Request) -> web.Response:
    """List installed extensions from .likecodex/extensions/ directory."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    extensions_dir = Path(working_dir) / ".likecodex" / "extensions"
    extensions = []
    if extensions_dir.exists():
        for child in sorted(extensions_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest_file = child / "manifest.json"
            if not manifest_file.exists():
                continue
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                extensions.append({
                    "id": manifest.get("id", child.name),
                    "name": manifest.get("name", child.name),
                    "version": manifest.get("version", "0.0.0"),
                    "description": manifest.get("description", ""),
                    "author": manifest.get("author", ""),
                    "enabled": manifest.get("enabled", True),
                    "main": manifest.get("main", ""),
                    "contributes": manifest.get("contributes", {}),
                })
            except Exception:
                continue
    return web.json_response(extensions)


async def ide_extensions_toggle(request: web.Request) -> web.Response:
    """Enable or disable an extension."""
    cfg = _resolve_config(request.app[APP_CONFIG])
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    ext_id = data.get("id", "")
    enabled = data.get("enabled", True)
    ext_dir = Path(working_dir) / ".likecodex" / "extensions" / ext_id
    manifest_file = ext_dir / "manifest.json"
    if not manifest_file.exists():
        return web.json_response({"error": "Extension not found"}, status=404)
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest["enabled"] = enabled
        manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return web.json_response({"success": True, "id": ext_id, "enabled": enabled})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


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

    # ── Workspace API endpoints ─────────────────────────────
    app.router.add_get("/workspace/list", workspace_list)
    app.router.add_get("/workspace/read", workspace_read)
    app.router.add_post("/workspace/write", workspace_write)

    # ── Inline Edit API ──────────────────────────────────────
    app.router.add_post("/inline-edit", inline_edit)

    # ── IDE Completion API ───────────────────────────────────
    app.router.add_post("/api/ide/completion/inline", ide_inline_completion)
    app.router.add_post("/api/ide/completion/accepted", ide_completion_accepted)

    # ── IDE Context Search API (@ mentions) ──────────────────
    app.router.add_get("/api/ide/context/search", ide_context_search)

    # ── IDE LSP API ──────────────────────────────────────────
    app.router.add_post("/api/ide/lsp/definition", ide_lsp_definition)
    app.router.add_post("/api/ide/lsp/references", ide_lsp_references)
    app.router.add_post("/api/ide/lsp/hover", ide_lsp_hover)
    app.router.add_get("/api/ide/lsp/diagnostics", ide_lsp_diagnostics)

    # ── IDE Composer API (multi-file AI editing) ─────────────
    app.router.add_post("/api/ide/composer/chat", ide_composer_chat)

    # ── IDE Git API (version control) ────────────────────────
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

    # ── IDE Terminal API (AI-powered terminal) ────────────────
    app.router.add_post("/api/ide/terminal/create", ide_terminal_create)
    app.router.add_post("/api/ide/terminal/execute", ide_terminal_execute)
    app.router.add_post("/api/ide/terminal/stream", ide_terminal_stream)
    app.router.add_post("/api/ide/terminal/suggest", ide_terminal_suggest)
    app.router.add_post("/api/ide/terminal/diagnose", ide_terminal_diagnose)
    app.router.add_post("/api/ide/terminal/close", ide_terminal_close)

    # ── IDE Debug / Test API ───────────────────────────────────
    app.router.add_get("/api/ide/tests/discover", ide_tests_discover)
    app.router.add_post("/api/ide/tests/run", ide_tests_run)
    app.router.add_post("/api/ide/debug/analyze", ide_debug_analyze)

    # ── IDE Settings API ───────────────────────────────────
    app.router.add_get("/api/ide/settings", ide_settings_get_all)
    app.router.add_get("/api/ide/settings/categories", ide_settings_categories)
    app.router.add_post("/api/ide/settings", ide_settings_set)
    app.router.add_post("/api/ide/settings/reset", ide_settings_reset)
    app.router.add_post("/api/ide/settings/reset-all", ide_settings_reset_all)
    app.router.add_get("/api/ide/settings/keybindings", ide_keybindings_get)
    app.router.add_post("/api/ide/settings/keybindings", ide_keybindings_set)
    app.router.add_post("/api/ide/settings/keybindings/reset", ide_keybindings_reset)

    # ── IDE Extensions API ─────────────────────────────────
    app.router.add_get("/api/ide/extensions/list", ide_extensions_list)
    app.router.add_post("/api/ide/extensions/toggle", ide_extensions_toggle)

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
