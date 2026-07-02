"""IDE API route handlers.

Handles: workspace (list/read/write), inline edit, completion,
context search, composer, settings, extensions, debug, tests.
"""

from __future__ import annotations

import json
import logging
import os
import re
import textwrap
import uuid
from pathlib import Path
from typing import Any

from aiohttp import web

from likecodex_engine.llm.base import Message, Role
from likecodex_engine.llm.factory import create_provider, provider_from_config

from likecodex_engine.routes._shared import (
    _cfg_wd,
    _resolve_config,
    _make_sse_response,
    _sse_write,
    _sse_done,
    _SSEKeepalive,
    APP_CONFIG,
)

logger = logging.getLogger(__name__)

# Lazy-initialized services
_completion_service: Any = None
_settings_manager: Any = None
_test_runner: Any = None


def _reset_services() -> None:
    """Reset all lazy-init services (called during shutdown)."""
    global _completion_service, _settings_manager, _test_runner, _terminal_manager
    _completion_service = None
    _settings_manager = None
    _test_runner = None
    _terminal_manager = None


def _get_completion_service():
    global _completion_service
    if _completion_service is None:
        from likecodex_engine.completion.inline import InlineCompletionService
        _completion_service = InlineCompletionService()
    return _completion_service


def _get_settings_manager(working_dir: str):
    global _settings_manager
    if _settings_manager is None:
        from likecodex_engine.settings.manager import SettingsManager
        _settings_manager = SettingsManager(working_dir)
    return _settings_manager


def _get_test_runner(working_dir: str):
    global _test_runner
    if _test_runner is None:
        from likecodex_engine.debug.test_runner import TestRunnerService
        _test_runner = TestRunnerService(working_dir)
    return _test_runner


# ── Workspace API ─────────────────────────────────────────────


def _workspace_path(request: web.Request, rel_path: str) -> tuple[Path, Path] | web.Response:
    _, wd = _cfg_wd(request)
    working_dir = Path(wd)
    target = (working_dir / rel_path).resolve()
    if not str(target).startswith(str(working_dir.resolve())):
        return web.json_response({"error": "Path outside workspace"}, status=403)
    return working_dir, target


async def workspace_list(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    working_dir = Path(wd)
    rel_path = request.query.get("path", ".")
    depth_str = request.query.get("depth", "1")
    try:
        depth = int(depth_str)
    except ValueError:
        depth = 1

    target = (working_dir / rel_path).resolve()
    if not str(target).startswith(str(working_dir.resolve())):
        return web.json_response({"error": "Path outside workspace"}, status=403)
    if not target.exists():
        return web.json_response({"error": "Path not found"}, status=404)

    result: dict = {"name": target.name, "path": str(target.relative_to(working_dir)), "type": "directory" if target.is_dir() else "file"}

    if target.is_dir():
        children = []
        try:
            for entry in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if entry.name.startswith(".") and entry.name not in (".gitignore", ".env.example", ".editorconfig"):
                    continue
                if entry.name in ("node_modules", "target", "__pycache__", ".git", ".next", "out"):
                    continue
                child = {
                    "name": entry.name,
                    "path": str(entry.relative_to(working_dir)),
                    "type": "directory" if entry.is_dir() else "file",
                }
                if entry.is_file():
                    try:
                        child["size"] = entry.stat().st_size
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
    rel_path = request.query.get("path", "")
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)

    resolved = _workspace_path(request, rel_path)
    if isinstance(resolved, web.Response):
        return resolved
    _, target = resolved
    if not target.exists() or not target.is_file():
        return web.json_response({"error": "File not found"}, status=404)

    try:
        if target.stat().st_size > 1024 * 1024:
            return web.json_response({"error": "File too large"}, status=413)
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return web.json_response({"error": f"Cannot read file: {e}"}, status=500)

    return web.json_response({"path": rel_path, "name": target.name, "content": content, "size": target.stat().st_size})


async def workspace_write(request: web.Request) -> web.Response:
    data = await request.json()
    rel_path = data.get("path", "")
    content = data.get("content", "")
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)

    resolved = _workspace_path(request, rel_path)
    if isinstance(resolved, web.Response):
        return resolved
    _, target = resolved

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        return web.json_response({"error": f"Cannot write file: {e}"}, status=500)

    return web.json_response({"ok": True, "path": rel_path, "size": target.stat().st_size})


# ── Inline Edit API ───────────────────────────────────────────


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
        snippet = textwrap.dedent(full_content)
        context_section = f"## Full file context ({language}):\n```{language}\n{snippet}\n```\n\n"

    messages = [
        Message(role=Role.SYSTEM, content=INLINE_EDIT_SYSTEM),
        Message(role=Role.USER, content=INLINE_EDIT_USER.format(
            language=language, context_section=context_section, code=code, instruction=instruction,
        )),
    ]

    try:
        response = await llm.complete(messages, temperature=0.1, max_tokens=4096)
    except Exception as e:
        return web.json_response({"error": f"LLM call failed: {e}"}, status=502)

    raw = response.content.strip()
    code_block_match = re.search(r"```(?:\w+)?\n(.*?)\n```", raw, re.DOTALL)
    modified = code_block_match.group(1).strip() if code_block_match else raw

    return web.json_response({"original": code, "modified": modified, "explanation": "", "model": response.model, "usage": response.usage})


# ── IDE Completion API ─────────────────────────────────────────


async def ide_inline_completion(request: web.Request) -> web.Response:
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
        return web.json_response({"error": f"Failed to create LLM provider: {e}"}, status=500)

    from likecodex_engine.completion.inline import InlineCompletionRequest

    req = InlineCompletionRequest(
        file_path=file_path, language=language, prefix=prefix[-2000:],
        suffix=suffix[:500], imports=imports if isinstance(imports, list) else [],
        current_scope=current_scope, cursor_line=cursor_line, cursor_col=cursor_col,
    )

    service = _get_completion_service()
    result = await service.complete(req, llm=llm)

    if result:
        return web.json_response({"text": result.text, "completion_id": result.completion_id, "model": result.model, "latency_ms": result.latency_ms, "cache_hit": result.cache_hit})
    return web.json_response({"text": None})


async def ide_completion_accepted(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


# ── IDE Context Search API (@ mentions) ────────────────────────


async def ide_context_search(request: web.Request) -> web.Response:
    query = request.query.get("q", "")
    _, wd = _cfg_wd(request)
    from likecodex_engine.context.mention_search import MentionSearchService
    service = MentionSearchService(Path(wd))
    results = await service.search(query, limit=20)
    return web.json_response({"results": results})


# ── IDE Composer API ───────────────────────────────────────────


async def ide_composer_chat(request: web.Request) -> web.StreamResponse:
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
            async for event in agent.execute(message=message, mentions=mentions, session_id=session_id):
                payload = json.dumps(event)
                await _sse_write(response, payload)
        except Exception as exc:
            error_event = json.dumps({"type": "error", "content": str(exc)})
            await _sse_write(response, error_event)

    await _sse_done(response)
    return response


# ── Settings API ───────────────────────────────────────────────


async def ide_settings_get_all(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    return web.json_response({"settings": _get_settings_manager(wd).get_all()})


async def ide_settings_categories(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    return web.json_response({"categories": _get_settings_manager(wd).get_categories()})


async def ide_settings_set(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    key = data.get("key", "")
    value = data.get("value")
    mgr = _get_settings_manager(wd)
    mgr.set(key, value)
    return web.json_response({"success": True, "key": key, "value": mgr.get(key)})


async def ide_settings_reset(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    key = data.get("key", "")
    mgr = _get_settings_manager(wd)
    mgr.reset(key)
    return web.json_response({"success": True, "key": key, "value": mgr.get(key)})


async def ide_settings_reset_all(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    mgr = _get_settings_manager(wd)
    mgr.reset_all()
    return web.json_response({"success": True, "settings": mgr.get_all()})


async def ide_keybindings_get(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    mgr = _get_settings_manager(wd)
    return web.json_response({"keybindings": mgr.get_keybindings(), "conflicts": mgr.check_conflicts()})


async def ide_keybindings_set(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    mgr = _get_settings_manager(wd)
    mgr.set_keybinding(data.get("id", ""), data.get("keys", []))
    return web.json_response({"success": True, "conflicts": mgr.check_conflicts()})


async def ide_keybindings_reset(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    mgr = _get_settings_manager(wd)
    mgr.reset_keybindings()
    return web.json_response({"keybindings": mgr.get_keybindings(), "conflicts": mgr.check_conflicts()})


# ── Extensions API ─────────────────────────────────────────────


async def ide_extensions_list(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    extensions_dir = Path(wd) / ".likecodex" / "extensions"
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
    _, wd = _cfg_wd(request)
    data = await request.json()
    ext_id = data.get("id", "")
    enabled = data.get("enabled", True)
    ext_dir = Path(wd) / ".likecodex" / "extensions" / ext_id
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


# ── Terminal API ──────────────────────────────────────────────

_terminal_manager: Any = None


def _get_terminal_manager(working_dir: str):
    global _terminal_manager
    if _terminal_manager is None:
        from likecodex_engine.terminal.pty_manager import TerminalManager
        _terminal_manager = TerminalManager(working_dir)
    return _terminal_manager


def _create_terminal_llm(cfg: dict):
    from likecodex_engine.terminal.ai_assistant import TerminalAIAssistant
    return TerminalAIAssistant(provider_from_config(cfg, thinking=False))


async def ide_terminal_create(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    manager = _get_terminal_manager(wd)
    data = await request.json()
    session_id = data.get("id") or f"term-{uuid.uuid4()}"
    cwd = data.get("cwd", wd)
    session = manager.create_session(session_id, cwd=cwd)
    return web.json_response({"id": session.id, "cwd": session.cwd, "shell": session.shell})


async def ide_terminal_execute(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    manager = _get_terminal_manager(wd)
    data = await request.json()
    result = await manager.execute_command(data.get("sessionId", "term-default"), data.get("command", ""))
    return web.json_response(result)


async def ide_terminal_stream(request: web.Request) -> web.StreamResponse:
    _, wd = _cfg_wd(request)
    manager = _get_terminal_manager(wd)
    data = await request.json()
    session_id = data.get("sessionId", "term-default")
    command = data.get("command", "")
    response = _make_sse_response()
    await response.prepare(request)
    try:
        async for event in manager.execute_command_stream(session_id, command):
            payload = json.dumps(event)
            await _sse_write(response, payload)
    except Exception as exc:
        error_event = json.dumps({"type": "error", "content": str(exc)})
        await _sse_write(response, error_event)
    await _sse_done(response)
    return response


async def ide_terminal_suggest(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    data = await request.json()
    description = data.get("description", "")
    if not description:
        return web.json_response({"command": "", "error": "Description required"}, status=400)
    assistant = _create_terminal_llm(cfg)
    command = await assistant.suggest_command(description)
    return web.json_response({"command": command})


async def ide_terminal_diagnose(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    data = await request.json()
    assistant = _create_terminal_llm(cfg)
    diagnosis = await assistant.diagnose_error(data.get("command", ""), data.get("error", ""))
    return web.json_response({"diagnosis": diagnosis})


async def ide_terminal_close(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    data = await request.json()
    success = _get_terminal_manager(wd).close_session(data.get("sessionId", ""))
    return web.json_response({"success": success})


# ── Debug / Test API ───────────────────────────────────────────


async def ide_tests_discover(request: web.Request) -> web.Response:
    _, wd = _cfg_wd(request)
    result = await _get_test_runner(wd).discover_tests()
    return web.json_response(result)


async def ide_tests_run(request: web.Request) -> web.StreamResponse:
    _, wd = _cfg_wd(request)
    data = await request.json()
    test_filter = data.get("filter", "")

    response = _make_sse_response()
    await response.prepare(request)

    try:
        async for event in _get_test_runner(wd).run_tests(test_filter=test_filter):
            payload = json.dumps(event)
            await _sse_write(response, payload)
    except Exception as exc:
        error_event = json.dumps({"type": "error", "content": str(exc)})
        await _sse_write(response, error_event)

    await _sse_done(response)
    return response


async def ide_debug_analyze(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    data = await request.json()
    from likecodex_engine.debug.ai_debug import AIDebugAssistant
    assistant = AIDebugAssistant(provider_from_config(cfg, thinking=False))
    result = await assistant.analyze_error(
        error_message=data.get("errorMessage", ""),
        stack_trace=data.get("stackTrace", ""),
        relevant_code=data.get("relevantCode", ""),
        file_path=data.get("filePath", ""),
    )
    return web.json_response(result)


def register_routes(app: web.Application, config: dict) -> None:
    # Workspace
    app.router.add_get("/workspace/list", workspace_list)
    app.router.add_get("/workspace/read", workspace_read)
    app.router.add_post("/workspace/write", workspace_write)
    # Inline Edit
    app.router.add_post("/inline-edit", inline_edit)
    # Completion
    app.router.add_post("/api/ide/completion/inline", ide_inline_completion)
    app.router.add_post("/api/ide/completion/accepted", ide_completion_accepted)
    # Context Search
    app.router.add_get("/api/ide/context/search", ide_context_search)
    # Composer
    app.router.add_post("/api/ide/composer/chat", ide_composer_chat)
    # Settings
    app.router.add_get("/api/ide/settings", ide_settings_get_all)
    app.router.add_get("/api/ide/settings/categories", ide_settings_categories)
    app.router.add_post("/api/ide/settings", ide_settings_set)
    app.router.add_post("/api/ide/settings/reset", ide_settings_reset)
    app.router.add_post("/api/ide/settings/reset-all", ide_settings_reset_all)
    app.router.add_get("/api/ide/settings/keybindings", ide_keybindings_get)
    app.router.add_post("/api/ide/settings/keybindings", ide_keybindings_set)
    app.router.add_post("/api/ide/settings/keybindings/reset", ide_keybindings_reset)
    # Extensions
    app.router.add_get("/api/ide/extensions/list", ide_extensions_list)
    app.router.add_post("/api/ide/extensions/toggle", ide_extensions_toggle)
    # Terminal
    app.router.add_post("/api/ide/terminal/create", ide_terminal_create)
    app.router.add_post("/api/ide/terminal/execute", ide_terminal_execute)
    app.router.add_post("/api/ide/terminal/stream", ide_terminal_stream)
    app.router.add_post("/api/ide/terminal/suggest", ide_terminal_suggest)
    app.router.add_post("/api/ide/terminal/diagnose", ide_terminal_diagnose)
    app.router.add_post("/api/ide/terminal/close", ide_terminal_close)
    # Debug / Test
    app.router.add_get("/api/ide/tests/discover", ide_tests_discover)
    app.router.add_post("/api/ide/tests/run", ide_tests_run)
    app.router.add_post("/api/ide/debug/analyze", ide_debug_analyze)
