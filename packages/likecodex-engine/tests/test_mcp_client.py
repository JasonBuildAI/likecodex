"""Tests for persistent MCP client."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from likecodex_engine.mcp.client import McpClient


@pytest.mark.asyncio
async def test_mcp_client_list_and_call_tools() -> None:
    mock_server = Path(__file__).with_name("mock_mcp_server.py")
    client = McpClient(sys.executable, [str(mock_server)])
    try:
        tools = await client.list_tools()
        assert any(t.get("name") == "echo" for t in tools)
        result = await client.call_tool("echo", {"message": "hello"})
        assert "result" in result or "error" not in result
        content = result.get("result", {})
        if isinstance(content, dict) and "content" in content:
            assert content
    finally:
        await client.close()
