"""Load MCP servers and register their tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from likecodex_engine.mcp.manager import global_mcp_manager
from likecodex_engine.tools.registry import ToolRegistry


def _default_servers_path() -> Path:
    return Path(__file__).with_name("servers.json")


def _load_mcp_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    servers: dict[str, Any] = {}
    for name, cfg in data.get("mcpServers", {}).items():
        if not isinstance(cfg, dict):
            continue
        command = cfg.get("command")
        if not command:
            continue
        servers[name] = {
            "command": command,
            "args": cfg.get("args", []),
            "env": cfg.get("env", {}),
            "enabled": True,
            "startup": "lazy",
        }
    return servers


def discover_mcp_servers(config: dict[str, Any], working_dir: str | Path) -> dict[str, Any]:
    """Merge MCP server definitions from config, JSON, and defaults."""
    servers: dict[str, Any] = {}
    working_dir = Path(working_dir)

    servers_path = Path(config.get("mcp_servers_path", _default_servers_path()))
    if servers_path.exists():
        servers.update(json.loads(servers_path.read_text(encoding="utf-8")))

    for mcp_json in (working_dir / ".mcp.json", Path.home() / ".likecodex" / ".mcp.json"):
        servers.update(_load_mcp_json(mcp_json))

    raw_servers = config.get("mcp_servers") or {}
    for name, cfg in raw_servers.items():
        if isinstance(cfg, dict):
            servers[name] = {**servers.get(name, {}), **cfg}

    default_startup = str(config.get("mcp_startup", "lazy")).lower()
    normalized: dict[str, Any] = {}
    for name in sorted(servers.keys()):
        cfg = dict(servers[name])
        if not cfg.get("command"):
            continue
        cfg.setdefault("enabled", True)
        cfg.setdefault("startup", default_startup)
        normalized[name] = cfg
    return normalized


async def register_mcp_tools(
    registry: ToolRegistry,
    config: dict[str, Any] | None = None,
    *,
    eager_only: bool = False,
) -> list[str]:
    """Discover MCP tools and register them on the registry."""
    config = config or {}
    working_dir = config.get("working_dir", ".")
    servers = discover_mcp_servers(config, working_dir)
    manager = global_mcp_manager()
    manager.configure(servers)

    registered: list[str] = []
    for server_name, server_cfg in servers.items():
        if not server_cfg.get("enabled", True):
            continue
        startup = str(server_cfg.get("startup", "lazy")).lower()
        if eager_only and startup != "eager":
            continue

        try:
            tools = await manager.list_tools(server_name)
        except Exception as exc:
            registry.register(
                f"mcp__{server_name}__error",
                {
                    "description": f"MCP server {server_name} failed to connect: {exc}",
                    "parameters": {"type": "object", "properties": {}},
                },
                _error_handler(str(exc)),
                read_only=True,
            )
            continue

        for tool in tools:
            tool_name = tool.get("name")
            if not tool_name:
                continue
            registered_name = f"mcp__{server_name}__{tool_name}"

            async def handler(
                _server: str = server_name,
                _tool: str = tool_name,
                **kwargs: Any,
            ) -> str:
                result = await manager.call_tool(_server, _tool, kwargs)
                return json.dumps(result)

            registry.register(
                registered_name,
                {
                    "description": tool.get("description", f"MCP tool {tool_name}"),
                    "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                },
                handler,
            )
            registered.append(registered_name)
    return registered


def _error_handler(message: str):
    async def handler(**_: Any) -> str:
        return json.dumps({"error": message})

    return handler


def mcp_tool_to_openai_format(
    server_name: str,
    tool: dict[str, Any],
) -> dict[str, Any]:
    """Convert a raw MCP tool definition to OpenAI-compatible function calling format.

    Handles both MCP inputSchema (JSON Schema) and simplified schemas.
    Auto-prefixes the tool name with mcp__{server_name} for disambiguation.
    """
    raw_name = tool.get("name", "unknown")
    input_schema = tool.get("inputSchema") or {}

    # Normalize parameters: ensure it has type="object" and properties
    parameters = {"type": "object", "properties": {}}
    if isinstance(input_schema, dict):
        if "type" in input_schema:
            parameters = dict(input_schema)
        if "properties" in input_schema:
            parameters["properties"] = dict(input_schema["properties"])
        if "required" in input_schema:
            parameters["required"] = list(input_schema["required"])

    return {
        "type": "function",
        "function": {
            "name": f"mcp__{server_name}__{raw_name}",
            "description": tool.get("description", f"MCP tool from {server_name}: {raw_name}"),
            "parameters": parameters,
        },
    }


def convert_all_mcp_tools(
    server_name: str,
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert all tools from an MCP server to OpenAI format in one call."""
    return [mcp_tool_to_openai_format(server_name, t) for t in tools if t.get("name")]
