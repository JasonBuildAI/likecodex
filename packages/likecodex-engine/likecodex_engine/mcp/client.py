"""Persistent MCP stdio session."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"


class McpClient:
    """Long-lived MCP server connection over stdio JSON-RPC."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._request_id = 0
        self._initialized = False

    async def start(self) -> None:
        if self._proc and self._proc.returncode is None:
            return
        merged_env = {**dict(os.environ), **self.env}
        self._proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )
        await self._initialize()

    async def close(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=3)
            except TimeoutError:
                self._proc.kill()
                await self._proc.wait()
        self._proc = None
        self._initialized = False

    async def _initialize(self) -> None:
        result = await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "likecodex", "version": "0.1.0"},
            },
        )
        if "error" in result:
            raise RuntimeError(f"MCP initialize failed: {result['error']}")
        await self._notify("notifications/initialized", {})
        self._initialized = True

    async def list_tools(self) -> list[dict[str, Any]]:
        await self.start()
        result = await self._request("tools/list", {})
        if "error" in result:
            logger.warning("MCP tools/list error: %s", result["error"])
            return []
        return list(result.get("result", {}).get("tools", []))

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self.start()
        return await self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=120,
        )

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        line = (json.dumps(payload) + "\n").encode()
        self._proc.stdin.write(line)
        await self._proc.stdin.drain()

    async def _request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30,
        retries: int = 2,
    ) -> dict[str, Any]:
        last_error: dict[str, Any] = {"error": "no response"}
        for attempt in range(retries + 1):
            try:
                return await self._request_once(method, params, timeout)
            except (BrokenPipeError, ConnectionResetError, RuntimeError) as exc:
                last_error = {"error": str(exc)}
                logger.warning("MCP request failed (%s), reconnecting", exc)
                await self.close()
                if attempt < retries:
                    await self.start()
        return last_error

    async def _request_once(
        self,
        method: str,
        params: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        async with self._lock:
            if not self._proc or not self._proc.stdin or not self._proc.stdout:
                raise RuntimeError("MCP process not running")

            self._request_id += 1
            req_id = self._request_id
            payload: dict[str, Any] = {
                "jsonrpc": "2.0",
                "method": method,
                "id": req_id,
            }
            if params is not None:
                payload["params"] = params

            line = (json.dumps(payload) + "\n").encode()
            self._proc.stdin.write(line)
            await self._proc.stdin.drain()

            while True:
                raw = await asyncio.wait_for(self._proc.stdout.readline(), timeout=timeout)
                if not raw:
                    raise RuntimeError("MCP server closed stdout")
                text = raw.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    message = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if message.get("id") == req_id:
                    return message
                # Ignore notifications and unrelated responses.
