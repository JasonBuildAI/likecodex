"""Load MCP servers and register their tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from likecodex_engine.mcp.client import McpClient
from likecodex_engine.tools.registry import ToolRegistry


def _default_servers_path() -> Path:
    return Path(__file__).with_name("servers.json")


async def register_mcp_tools(
    registry: ToolRegistry,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """Discover MCP tools and register them on the registry."""
    config = config or {}
    servers: dict[str, Any] = {}

    servers_path = Path(config.get("mcp_servers_path", _default_servers_path()))
    if servers_path.exists():
        servers.update(json.loads(servers_path.read_text(encoding="utf-8")))

    servers.update(config.get("mcp_servers", {}))

    registered: list[str] = []
    for server_name, server_cfg in servers.items():
        if not server_cfg.get("enabled", True):
            continue
        command = server_cfg.get("command")
        if not command:
            continue
        client = McpClient(
            command=command,
            args=server_cfg.get("args", []),
            env=server_cfg.get("env", {}),
        )
        tools = await client.list_tools()
        for tool in tools:
            tool_name = tool.get("name")
            if not tool_name:
                continue
            registered_name = f"mcp_{server_name}_{tool_name}"

            async def handler(
                _client: McpClient = client,
                _tool_name: str = tool_name,
                **kwargs: Any,
            ) -> str:
                result = await _client.call_tool(_tool_name, kwargs)
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
