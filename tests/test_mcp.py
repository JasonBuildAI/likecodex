"""MCP loader tests."""

import pytest
from likecodex_engine.mcp.client import McpClient
from likecodex_engine.tools.registry import ToolRegistry


def test_mcp_client_list_tools_monkeypatch(monkeypatch):
    async def fake_request(self, payload):
        return {"result": {"tools": [{"name": "demo", "description": "demo tool"}]}}

    monkeypatch.setattr(McpClient, "_request", fake_request)

    async def run():
        client = McpClient("echo")
        tools = await client.list_tools()
        assert tools[0]["name"] == "demo"

    import asyncio

    asyncio.run(run())


@pytest.mark.asyncio
async def test_register_mcp_tools_empty_config(tmp_path):
    from likecodex_engine.mcp.loader import register_mcp_tools

    registry = ToolRegistry(str(tmp_path))
    registered = await register_mcp_tools(
        registry,
        {"mcp_servers": {}, "mcp_servers_path": str(tmp_path / "no-servers.json")},
    )
    assert registered == []
