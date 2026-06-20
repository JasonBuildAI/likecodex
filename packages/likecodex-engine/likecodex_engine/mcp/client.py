"""MCP (Model Context Protocol) client stub for external tool servers."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class McpClient:
    """Discovers and invokes tools from an external MCP server.

    This is a minimal stub using stdio transport. A production implementation
    would add SSE/WebSocket transports and full schema negotiation.
    """

    def __init__(self, command: str, args: list[str] | None = None, env: dict[str, str] | None = None) -> None:
        self.command = command
        self.args = args or []
        self.env = env or {}

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools exposed by the MCP server."""
        response = await self._request({"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        return response.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server."""
        return await self._request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
                "id": 2,
            }
        )

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**dict(__import__("os").environ), **self.env},
        )
        try:
            data = (json.dumps(payload) + "\n").encode()
            stdout, stderr = await asyncio.wait_for(proc.communicate(data), timeout=30)
            if proc.returncode != 0:
                return {"error": stderr.decode("utf-8", errors="replace")}
            return json.loads(stdout.decode("utf-8", errors="replace"))
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return {"error": "MCP request timed out"}
        except Exception as e:
            return {"error": str(e)}
