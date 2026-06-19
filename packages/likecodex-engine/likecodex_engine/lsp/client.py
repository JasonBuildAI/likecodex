"""LSP JSON-RPC client (minimal)."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class LspClient:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self._id = 0
        self._lock = asyncio.Lock()

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        async with self._lock:
            self._id += 1
            msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
            assert self.process.stdin is not None
            body = json.dumps(msg)
            self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}".encode())
            await self.process.stdin.drain()
            return await self._read_response()

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        async with self._lock:
            msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
            assert self.process.stdin is not None
            body = json.dumps(msg)
            self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}".encode())
            await self.process.stdin.drain()

    async def _read_response(self) -> Any:
        assert self.process.stdout is not None
        headers: dict[str, str] = {}
        while True:
            line = (await self.process.stdout.readline()).decode("utf-8", errors="replace").strip()
            if not line:
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length", "0"))
        if length <= 0:
            return None
        data = await self.process.stdout.readexactly(length)
        payload = json.loads(data.decode("utf-8"))
        return payload.get("result")

    async def close(self) -> None:
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2)
            except TimeoutError:
                self.process.kill()
