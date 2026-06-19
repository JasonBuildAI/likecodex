"""Tests for the HTTP bridge server."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from likecodex_engine.server import create_app


@pytest.mark.asyncio
async def test_health() -> None:
    app = create_app(
        {
            "provider": "mock",
            "model": "mock",
            "api_key": None,
            "base_url": None,
            "working_dir": ".",
            "approval_mode": "auto",
        }
    )
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_run_task() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = create_app(
            {
                "provider": "mock",
                "model": "mock",
                "api_key": None,
                "base_url": None,
                "working_dir": td,
                "approval_mode": "auto",
            }
        )
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/run", json={"prompt": "create hello.py and run it"})
            assert resp.status == 200
            data = await resp.json()
            outputs = data["outputs"]
            assert len(outputs) >= 3
            assert (Path(td) / "hello.py").exists()
