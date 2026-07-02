"""MCP API route handlers.

Handles: list MCP servers, get server status, connect/disconnect,
list tools, enable/disable tools, update server config.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import web

from likecodex_engine.mcp.loader import discover_mcp_servers
from likecodex_engine.mcp.manager import global_mcp_manager, ConnectionStatus

logger = logging.getLogger(__name__)


async def mcp_servers_list(request: web.Request) -> web.Response:
    """List all configured MCP servers with their status."""
    cfg = request.app.get("config", {})
    working_dir = cfg.get("working_dir", ".")
    servers = discover_mcp_servers(cfg, working_dir)
    manager = global_mcp_manager()
    result = []
    for name, srv_cfg in servers.items():
        status = manager.status(name)
        result.append({
            "name": name,
            "command": srv_cfg.get("command", ""),
            "args": srv_cfg.get("args", []),
            "enabled": srv_cfg.get("enabled", True),
            "startup": srv_cfg.get("startup", "lazy"),
            "status": status.value,
            "tools_count": len(manager._tool_schemas.get(name, [])),
        })
    return web.json_response({"servers": result})


async def mcp_server_status(request: web.Request) -> web.Response:
    """Get status of a specific MCP server."""
    name = request.query.get("name", "")
    if not name:
        return web.json_response({"error": "name query parameter required"}, status=400)
    manager = global_mcp_manager()
    status = manager.status(name)
    tools = manager._tool_schemas.get(name, [])
    return web.json_response({
        "name": name,
        "status": status.value,
        "tools": tools,
        "tools_count": len(tools),
    })


async def mcp_server_connect(request: web.Request) -> web.Response:
    """Connect to an MCP server."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    manager = global_mcp_manager()
    try:
        await manager.connect(name)
        tools = await manager.list_tools(name)
        # Cache tool schemas
        manager._tool_schemas[name] = tools
        return web.json_response({
            "ok": True,
            "name": name,
            "status": ConnectionStatus.CONNECTED.value,
            "tools_count": len(tools),
        })
    except Exception as e:
        return web.json_response({
            "ok": False,
            "name": name,
            "status": ConnectionStatus.ERROR.value,
            "error": str(e),
        }, status=500)


async def mcp_server_disconnect(request: web.Request) -> web.Response:
    """Disconnect from an MCP server."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    manager = global_mcp_manager()
    await manager.disconnect(name)
    return web.json_response({"ok": True, "name": name})


async def mcp_tools_list(request: web.Request) -> web.Response:
    """List all MCP tools across all connected servers."""
    manager = global_mcp_manager()
    all_tools = manager.get_all_tool_schemas()
    # Also get per-server tools
    per_server = {}
    for name in manager._tool_schemas:
        tools = manager._tool_schemas[name]
        per_server[name] = [
            {
                "name": t.get("name", "unknown"),
                "description": t.get("description", ""),
                "server": name,
                "enabled": True,
            }
            for t in tools
        ]
    return web.json_response({
        "tools": all_tools,
        "per_server": per_server,
    })


async def mcp_server_config_update(request: web.Request) -> web.Response:
    """Update MCP server configuration."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    
    cfg = request.app.get("config", {})
    working_dir = cfg.get("working_dir", ".")
    servers_path = Path(working_dir) / ".likecodex" / ".mcp.json"
    
    # Load existing config
    existing = {}
    if servers_path.exists():
        existing = json.loads(servers_path.read_text(encoding="utf-8"))
    
    mcp_servers = existing.get("mcpServers", {})
    if name not in mcp_servers:
        mcp_servers[name] = {}
    
    # Update fields
    if "command" in data:
        mcp_servers[name]["command"] = data["command"]
    if "args" in data:
        mcp_servers[name]["args"] = data["args"]
    if "env" in data:
        mcp_servers[name]["env"] = data["env"]
    if "enabled" in data:
        mcp_servers[name]["enabled"] = data["enabled"]
    
    existing["mcpServers"] = mcp_servers
    servers_path.parent.mkdir(parents=True, exist_ok=True)
    servers_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    
    # Re-configure manager
    manager = global_mcp_manager()
    from likecodex_engine.mcp.loader import discover_mcp_servers
    servers = discover_mcp_servers(cfg, working_dir)
    manager.configure(servers)
    
    return web.json_response({"ok": True, "name": name})


async def mcp_server_delete(request: web.Request) -> web.Response:
    """Delete an MCP server configuration."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    
    cfg = request.app.get("config", {})
    working_dir = cfg.get("working_dir", ".")
    servers_path = Path(working_dir) / ".likecodex" / ".mcp.json"
    
    if servers_path.exists():
        existing = json.loads(servers_path.read_text(encoding="utf-8"))
        mcp_servers = existing.get("mcpServers", {})
        if name in mcp_servers:
            del mcp_servers[name]
            existing["mcpServers"] = mcp_servers
            servers_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    
    # Disconnect if connected
    manager = global_mcp_manager()
    await manager.disconnect(name)
    
    return web.json_response({"ok": True, "deleted": name})


async def mcp_test_connection(request: web.Request) -> web.Response:
    """Test connection to an MCP server."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return web.json_response({"error": "name is required"}, status=400)
    
    cfg = request.app.get("config", {})
    working_dir = cfg.get("working_dir", ".")
    from likecodex_engine.mcp.client import McpClient
    
    # Build config from request or existing
    servers = discover_mcp_servers(cfg, working_dir)
    server_cfg = servers.get(name, {})
    
    command = data.get("command", server_cfg.get("command", ""))
    args = data.get("args", server_cfg.get("args", []))
    env = data.get("env", server_cfg.get("env", {}))
    
    if not command:
        return web.json_response({"error": "command is required"}, status=400)
    
    client = McpClient(command=command, args=args, env=env)
    try:
        await client.start()
        tools = await client.list_tools()
        await client.close()
        return web.json_response({
            "ok": True,
            "connected": True,
            "tools_count": len(tools),
            "tools": [t.get("name") for t in tools],
        })
    except Exception as e:
        return web.json_response({
            "ok": False,
            "connected": False,
            "error": str(e),
        }, status=500)


def register_routes(app: web.Application, config: dict) -> None:
    app.router.add_get("/api/ide/mcp/servers", mcp_servers_list)
    app.router.add_get("/api/ide/mcp/status", mcp_server_status)
    app.router.add_post("/api/ide/mcp/connect", mcp_server_connect)
    app.router.add_post("/api/ide/mcp/disconnect", mcp_server_disconnect)
    app.router.add_get("/api/ide/mcp/tools", mcp_tools_list)
    app.router.add_post("/api/ide/mcp/config", mcp_server_config_update)
    app.router.add_delete("/api/ide/mcp/config", mcp_server_delete)
    app.router.add_post("/api/ide/mcp/test", mcp_test_connection)
