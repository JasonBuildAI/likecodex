"""MCP connection pool for multiple servers."""

from __future__ import annotations

from typing import Any

from likecodex_engine.mcp.client import McpClient


class McpManager:
    """Manages persistent MCP sessions keyed by server name."""

    def __init__(self) -> None:
        self._clients: dict[str, McpClient] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._tool_schemas: dict[str, list[dict[str, Any]]] = {}

    def get_all_tool_schemas(self) -> list[dict[str, Any]]:
        """Get all MCP tools as OpenAI-compatible schemas for tool registry."""
        all_tools = []
        for server_name, tools in self._tool_schemas.items():
            for tool in tools:
                prefixed_name = f"mcp__{server_name}__{tool.get('name', 'unknown')}"
                all_tools.append({
                    "type": "function",
                    "function": {
                        "name": prefixed_name,
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                    },
                })
        return all_tools

    def configure(self, servers: dict[str, dict[str, Any]]) -> None:
        self._configs = dict(servers)

    async def connect(self, server_name: str) -> McpClient:
        if server_name in self._clients:
            client = self._clients[server_name]
            await client.start()
            return client

        cfg = self._configs.get(server_name)
        if not cfg:
            raise KeyError(f"MCP server '{server_name}' is not configured")

        client = McpClient(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env", {}),
        )
        await client.start()
        self._clients[server_name] = client
        return client

    async def list_tools(self, server_name: str) -> list[dict[str, Any]]:
        client = await self.connect(server_name)
        return await client.list_tools()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        client = await self.connect(server_name)
        return await client.call_tool(tool_name, arguments)

    async def close_all(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    def server_names(self) -> list[str]:
        return sorted(self._configs.keys())


_GLOBAL_MANAGER = McpManager()


def global_mcp_manager() -> McpManager:
    return _GLOBAL_MANAGER
