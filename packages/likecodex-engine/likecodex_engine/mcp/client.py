"""MCP (Model Context Protocol) client for external tool servers."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any


class McpClient:
    """Discovers and invokes tools from an external MCP server via stdio."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._tools_cache: list[dict[str, Any]] | None = None

    async def list_tools(self) -> list[dict[str, Any]]:
        if self._tools_cache is not None:
            return self._tools_cache
        response = await self._request({"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        tools = response.get("result", {}).get("tools", [])
        self._tools_cache = tools
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
                "id": 2,
            }
        )

    def _allowed_env(self) -> dict[str, str]:
        base = {
            k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "USERPROFILE", "SystemRoot", "TEMP", "TMP"}
        }
        base.update(self.env)
        return base

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._allowed_env(),
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
