"""MCP connection pool for multiple servers."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from likecodex_engine.mcp.client import McpClient

logger = logging.getLogger(__name__)


class ConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class McpManager:
    """Manages persistent MCP sessions keyed by server name."""

    def __init__(self) -> None:
        self._clients: dict[str, McpClient] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._tool_schemas: dict[str, list[dict[str, Any]]] = {}
        self._status: dict[str, ConnectionStatus] = {}

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
        for name in self._configs:
            self._status.setdefault(name, ConnectionStatus.DISCONNECTED)

    def status(self, server_name: str) -> ConnectionStatus:
        return self._status.get(server_name, ConnectionStatus.DISCONNECTED)

    def all_statuses(self) -> dict[str, ConnectionStatus]:
        return dict(self._status)

    async def connect(self, server_name: str) -> McpClient:
        if server_name in self._clients:
            client = self._clients[server_name]
            self._status[server_name] = ConnectionStatus.CONNECTING
            try:
                await client.start()
                self._status[server_name] = ConnectionStatus.CONNECTED
            except Exception as e:
                self._status[server_name] = ConnectionStatus.ERROR
                logger.warning("MCP reconnect failed for %s: %s", server_name, e)
                raise
            return client

        cfg = self._configs.get(server_name)
        if not cfg:
            raise KeyError(f"MCP server '{server_name}' is not configured")

        self._status[server_name] = ConnectionStatus.CONNECTING
        try:
            client = McpClient(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env", {}),
            )
            await client.start()
            self._clients[server_name] = client
            self._status[server_name] = ConnectionStatus.CONNECTED
        except Exception as e:
            self._status[server_name] = ConnectionStatus.ERROR
            logger.error("MCP connect failed for %s: %s", server_name, e)
            raise
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
        for name in self._status:
            self._status[name] = ConnectionStatus.DISCONNECTED

    def server_names(self) -> list[str]:
        return sorted(self._configs.keys())

    async def disconnect(self, server_name: str) -> None:
        client = self._clients.pop(server_name, None)
        if client:
            await client.close()
        self._status[server_name] = ConnectionStatus.DISCONNECTED


_GLOBAL_MANAGER = McpManager()


def global_mcp_manager() -> McpManager:
    return _GLOBAL_MANAGER
