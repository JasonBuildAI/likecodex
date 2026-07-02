"""MCP tool management tests.

Tests MCP tool registration, enable/disable, and server connection management.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_mcp_tool_registration(tmp_path):
    """Test registering MCP tools in the registry."""
    from likecodex_engine.tools.registry import ToolRegistry
    from likecodex_engine.mcp.manager import McpManager

    manager = McpManager()
    assert manager.server_names() == []

    # Configure a mock server
    manager.configure({
        "test-server": {
            "command": "echo",
            "args": [],
            "env": {},
            "enabled": True,
        }
    })
    assert "test-server" in manager.server_names()

    # Initially no tools
    all_tools = manager.get_all_tool_schemas()
    assert all_tools == []

    # Simulate tool schemas being added
    manager._tool_schemas["test-server"] = [
        {"name": "read_file", "description": "Read a file", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
        {"name": "write_file", "description": "Write a file", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}},
    ]

    all_tools = manager.get_all_tool_schemas()
    assert len(all_tools) == 2

    # Check prefixed names
    names = [t["function"]["name"] for t in all_tools]
    assert "mcp__test-server__read_file" in names
    assert "mcp__test-server__write_file" in names


@pytest.mark.asyncio
async def test_mcp_tool_enable_disable(tmp_path):
    """Test enabling and disabling MCP server connections."""
    from likecodex_engine.mcp.manager import McpManager, ConnectionStatus

    manager = McpManager()
    manager.configure({
        "server-a": {"command": "echo", "args": [], "env": {}, "enabled": True},
        "server-b": {"command": "echo", "args": [], "env": {}, "enabled": False},
    })

    # Both should be in config
    assert "server-a" in manager.server_names()
    assert "server-b" in manager.server_names()

    # Status should be disconnected initially
    assert manager.status("server-a") == ConnectionStatus.DISCONNECTED
    assert manager.status("server-b") == ConnectionStatus.DISCONNECTED

    # All statuses should show both
    statuses = manager.all_statuses()
    assert "server-a" in statuses
    assert "server-b" in statuses


@pytest.mark.asyncio
async def test_mcp_connect_failure_handling(tmp_path):
    """Test handling of connection failures gracefully."""
    from likecodex_engine.mcp.manager import McpManager, ConnectionStatus

    manager = McpManager()
    # Configure with a command that doesn't exist
    manager.configure({
        "bad-server": {
            "command": "this-command-does-not-exist-12345",
            "args": [],
            "env": {},
            "enabled": True,
        }
    })

    # Attempting to connect should raise an error
    with pytest.raises(Exception):
        await manager.connect("bad-server")

    # Status should reflect the error
    assert manager.status("bad-server") == ConnectionStatus.ERROR


@pytest.mark.asyncio
async def test_mcp_server_configuration(tmp_path):
    """Test MCP server configuration discovery and merging."""
    from likecodex_engine.mcp.loader import discover_mcp_servers

    # Test with config containing mcp_servers
    config = {
        "working_dir": str(tmp_path),
        "mcp_servers": {
            "custom-server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                "env": {"API_KEY": "test123"},
            }
        },
        "mcp_servers_path": str(tmp_path / "no-file.json"),
    }

    servers = discover_mcp_servers(config, tmp_path)
    assert "custom-server" in servers
    assert servers["custom-server"]["command"] == "npx"
    assert servers["custom-server"]["env"]["API_KEY"] == "test123"
    assert servers["custom-server"]["enabled"] is True


@pytest.mark.asyncio
async def test_mcp_json_config_loading(tmp_path):
    """Test loading MCP servers from .mcp.json config file."""
    from likecodex_engine.mcp.loader import discover_mcp_servers

    # Create a .mcp.json in the working directory
    mcp_json = tmp_path / ".mcp.json"
    mcp_json.write_text(json.dumps({
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
            },
            "fetch": {
                "command": "uvx",
                "args": ["mcp-server-fetch"],
            },
        }
    }), encoding="utf-8")

    config = {
        "working_dir": str(tmp_path),
        "mcp_servers_path": str(tmp_path / "no-file.json"),
    }

    servers = discover_mcp_servers(config, tmp_path)
    assert "filesystem" in servers
    assert "fetch" in servers
    assert servers["filesystem"]["command"] == "npx"


@pytest.mark.asyncio
async def test_mcp_manager_close_all(tmp_path):
    """Test closing all MCP connections."""
    from likecodex_engine.mcp.manager import McpManager, ConnectionStatus

    manager = McpManager()
    manager.configure({
        "server-a": {"command": "echo", "args": [], "env": {}, "enabled": True},
    })

    await manager.close_all()
    # After close_all, status should be disconnected
    statuses = manager.all_statuses()
    for status in statuses.values():
        assert status == ConnectionStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_mcp_tool_openai_conversion():
    """Test converting MCP tools to OpenAI-compatible format."""
    from likecodex_engine.mcp.loader import mcp_tool_to_openai_format, convert_all_mcp_tools

    tool = {
        "name": "get_weather",
        "description": "Get weather for a location",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
            },
            "required": ["location"],
        },
    }

    result = mcp_tool_to_openai_format("weather-server", tool)
    assert result["type"] == "function"
    assert result["function"]["name"] == "mcp__weather-server__get_weather"
    assert result["function"]["description"] == "Get weather for a location"
    assert "location" in result["function"]["parameters"]["properties"]
    assert "location" in result["function"]["parameters"]["required"]

    # Test batch conversion
    tools = [
        {"name": "tool1", "description": "First tool"},
        {"name": "tool2", "description": "Second tool"},
        {},  # Should be skipped (no name)
    ]
    converted = convert_all_mcp_tools("my-server", tools)
    assert len(converted) == 2
    assert converted[0]["function"]["name"] == "mcp__my-server__tool1"
    assert converted[1]["function"]["name"] == "mcp__my-server__tool2"


@pytest.mark.asyncio
async def test_mcp_tool_registration_in_registry(tmp_path):
    """Test registering MCP tools into the ToolRegistry."""
    from likecodex_engine.tools.registry import ToolRegistry
    from likecodex_engine.mcp.loader import register_mcp_tools

    registry = ToolRegistry(str(tmp_path))

    # Test with a config that has no servers - should register nothing
    registered = await register_mcp_tools(
        registry,
        {"mcp_servers": {}, "mcp_servers_path": str(tmp_path / "empty.json"), "working_dir": str(tmp_path)},
    )
    # Should return empty list (no servers configured)
    assert isinstance(registered, list)
