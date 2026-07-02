"""Skills API route handlers.

Handles: skills CRUD, list, detail, create, update, delete,
enable/disable, reload, invoke, install, export, import.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from aiohttp import web

from likecodex_engine.skills.loader import discover_skills, inject_dynamic_context
from likecodex_engine.skills.state import is_skill_enabled, set_skill_enabled
from likecodex_engine.skills.manager import (
    create_skill as _create_skill,
    validate_skill_name,
    update_skill as _update_skill,
    delete_skill as _delete_skill,
    install_skill_from_url as _install_skill,
    install_skill_from_marketplace as _install_marketplace,
    export_skill as _export_skill,
    import_skill as _import_skill,
    fetch_remote_index,
    search_remote_skills,
)

from likecodex_engine.routes._shared import (
    _ACTIVE_LOOPS,
    _resolve_config,
    _cfg_wd,
)

logger = logging.getLogger(__name__)


async def list_skills(request: web.Request) -> web.Response:
    cfg = _resolve_config(request.app[web.AppKey("config", dict)])
    working_dir = cfg.get("working_dir", ".")
    skills = discover_skills(working_dir)
    return web.json_response(
        {"skills": [{"name": s.name, "description": s.description, "source": s.source, "enabled": s.enabled} for s in skills]}
    )


async def ide_skills_list(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    skills = discover_skills(working_dir)
    return web.json_response({"skills": [s.to_dict() for s in skills]})


async def ide_skills_detail(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    name = request.query.get("name", "")
    if not name:
        return web.json_response({"error": "name query parameter is required"}, status=400)
    skills = discover_skills(working_dir)
    skill = next((s for s in skills if s.name == name), None)
    if not skill:
        return web.json_response({"error": f"Skill {name!r} not found"}, status=404)
    result = skill.to_dict()
    if skill.source_dir and skill.source_dir.is_dir():
        files = []
        for f in sorted(skill.source_dir.rglob("*")):
            if f.is_file():
                files.append(str(f.relative_to(skill.source_dir)))
        result["directory_files"] = files
    return web.json_response(result)


async def ide_skills_create(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    err = validate_skill_name(name)
    if err:
        return web.json_response({"error": err}, status=400)
    try:
        path = _create_skill(
            working_dir,
            name,
            description=data.get("description", ""),
            body=data.get("body", ""),
            run_as=data.get("run_as", "inline"),
            model=data.get("model"),
            allowed_tools=data.get("allowed_tools", []),
            author=data.get("author", ""),
            version=data.get("version", "0.1.0"),
        )
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    skills = discover_skills(working_dir)
    skill = next((s for s in skills if s.name == name), None)
    return web.json_response({"ok": True, "path": str(path), "skill": skill.to_dict() if skill else None})


async def ide_skills_update(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    fields = {}
    for key in ("description", "body", "run_as", "model", "allowed_tools"):
        if key in data:
            fields[key] = data[key]
    new_name = data.get("new_name") or data.get("name")
    if new_name and new_name != name:
        fields["name"] = new_name
    try:
        path = _update_skill(working_dir, name, **fields)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    if path is None:
        return web.json_response({"error": f"Skill {name!r} not found"}, status=404)
    skills = discover_skills(working_dir)
    updated_name = data.get("name", name)
    skill = next((s for s in skills if s.name == updated_name), None)
    return web.json_response({"ok": True, "path": str(path), "skill": skill.to_dict() if skill else None})


async def ide_skills_delete(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    try:
        ok = _delete_skill(working_dir, name)
    except PermissionError as e:
        return web.json_response({"error": str(e)}, status=403)
    if not ok:
        return web.json_response({"error": f"Skill {name!r} not found"}, status=404)
    return web.json_response({"ok": True, "deleted": name})


async def ide_skills_enable(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    current = is_skill_enabled(working_dir, name)
    set_skill_enabled(working_dir, name, not current)
    return web.json_response({"ok": True, "name": name, "enabled": not current})


async def ide_skills_reload(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    skills = discover_skills(working_dir)
    for sid, loop in _ACTIVE_LOOPS.items():
        if hasattr(loop, "tools") and hasattr(loop.tools, "_skill_runner"):
            loop.tools._skill_runner.reload()
    return web.json_response({"ok": True, "skills_count": len(skills), "skills": [s.to_dict() for s in skills]})


async def ide_skills_invoke(request: web.Request) -> web.Response:
    from likecodex_engine.agent.loop import build_subagent_loop

    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    name = data.get("name", "").strip()
    args = data.get("args", "")
    session_id = data.get("session_id", "")
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    skills = discover_skills(working_dir)
    skill = next((s for s in skills if s.name == name), None)
    if not skill:
        return web.json_response({"error": f"Skill {name!r} not found"}, status=404)
    body = inject_dynamic_context(skill.body, skill.source_dir)
    if args:
        body = body.replace("$ARGS", args).replace("$1", args)
    if skill.run_as == "subagent":
        if not session_id:
            return web.json_response({"error": "session_id required for subagent skills"}, status=400)
        from likecodex_engine.routes._shared import _resolve_loop
        loop = _resolve_loop(session_id)
        if loop is None:
            return web.json_response({"error": "Session not found"}, status=404)
        prompt = f"{skill.description}\n\n{body}"
        if args:
            prompt += f"\n\nArguments: {args}"
        subagent = build_subagent_loop(loop, skill.allowed_tools or None, None)
        parts: list[str] = []
        async for resp in subagent.run(prompt):
            if resp.event_type == "assistant" and resp.content:
                parts.append(resp.content)
        result_text = "\n".join(parts).strip()
        return web.json_response({"skill": name, "mode": "subagent", "result": result_text})
    return web.json_response({"skill": name, "mode": "inline", "body": body[:8000]})


async def ide_skills_install(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    url = data.get("url", "").strip()
    if not url:
        return web.json_response({"error": "url is required"}, status=400)
    try:
        path = _install_skill(working_dir, url)
    except FileExistsError as e:
        return web.json_response({"error": str(e)}, status=409)
    except subprocess.TimeoutExpired:
        return web.json_response({"error": "Git clone timed out"}, status=408)
    except RuntimeError as e:
        return web.json_response({"error": str(e)}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    skills = discover_skills(working_dir)
    skill_name = path.name
    skill = next((s for s in skills if s.name == skill_name), None)
    return web.json_response({"ok": True, "path": str(path), "skill": skill.to_dict() if skill else None})


async def ide_skills_export(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    name = request.query.get("name", "")
    if not name:
        return web.json_response({"error": "name query parameter is required"}, status=400)
    try:
        data = _export_skill(working_dir, name)
    except FileNotFoundError as e:
        return web.json_response({"error": str(e)}, status=404)
    return web.Response(body=data, status=200, headers={
        "Content-Type": "application/zip",
        "Content-Disposition": f'attachment; filename="{name}.zip"',
    })


async def ide_skills_import(request: web.Request) -> web.Response:
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    content_type = request.content_type or ""
    if content_type.startswith("multipart/"):
        reader = await request.multipart()
        field = await reader.next()
        if field is None:
            return web.json_response({"error": "No file uploaded"}, status=400)
        zip_data = await field.read(decode=False)
    else:
        data = await request.json()
        import base64
        zip_b64 = data.get("data", "")
        if not zip_b64:
            return web.json_response({"error": "multipart file or base64 data required"}, status=400)
        zip_data = base64.b64decode(zip_b64)
    try:
        names = _import_skill(working_dir, zip_data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.json_response({"ok": True, "imported": names, "count": len(names)})


async def ide_skills_marketplace(request: web.Request) -> web.Response:
    """Browse/search the skills marketplace."""
    q = request.query.get("q", "")
    try:
        if q:
            skills = await search_remote_skills(q)
        else:
            index = await fetch_remote_index()
            skills = index.get("skills", [])
        return web.json_response({"skills": skills})
    except Exception as e:
        return web.json_response({"skills": [], "error": str(e)})


async def ide_skills_marketplace_install(request: web.Request) -> web.Response:
    """Install a skill from the marketplace."""
    cfg, _ = _cfg_wd(request)
    working_dir = cfg.get("working_dir", ".")
    data = await request.json()
    name = data.get("name", "").strip()
    download_url = data.get("download_url", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    try:
        if download_url:
            if download_url.endswith(".git"):
                path = _install_skill(working_dir, download_url)
            else:
                # Download zip
                import httpx
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.get(download_url)
                    resp.raise_for_status()
                from likecodex_engine.skills.manager import _install_skill_from_zip_data
                path = _install_skill_from_zip_data(working_dir, name, resp.content)
        else:
            path = await _install_marketplace(working_dir, name)
    except FileExistsError as e:
        return web.json_response({"error": str(e)}, status=409)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    from likecodex_engine.skills.loader import discover_skills
    skills = discover_skills(working_dir)
    skill = next((s for s in skills if s.name == name), None)
    return web.json_response({"ok": True, "path": str(path), "skill": skill.to_dict() if skill else None})


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_get("/skills", list_skills)
    app.router.add_get("/api/ide/skills/list", ide_skills_list)
    app.router.add_get("/api/ide/skills/detail", ide_skills_detail)
    app.router.add_post("/api/ide/skills/create", ide_skills_create)
    app.router.add_put("/api/ide/skills/update", ide_skills_update)
    app.router.add_delete("/api/ide/skills/delete", ide_skills_delete)
    app.router.add_post("/api/ide/skills/enable", ide_skills_enable)
    app.router.add_post("/api/ide/skills/reload", ide_skills_reload)
    app.router.add_post("/api/ide/skills/invoke", ide_skills_invoke)
    app.router.add_post("/api/ide/skills/install", ide_skills_install)
    app.router.add_get("/api/ide/skills/export", ide_skills_export)
    app.router.add_post("/api/ide/skills/import", ide_skills_import)
    app.router.add_get("/api/ide/skills/marketplace", ide_skills_marketplace)
    app.router.add_post("/api/ide/skills/marketplace/install", ide_skills_marketplace_install)
