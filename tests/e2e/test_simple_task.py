"""End-to-end smoke tests for the LikeCodex agent engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from likecodex_engine.server import create_app


@pytest.mark.asyncio
async def test_create_and_run_python_script() -> None:
    """Engine can create a Python script and run it end-to-end."""
    with tempfile.TemporaryDirectory() as td:
        app = create_app(
            {
                "provider": "mock",
                "model": "mock",
                "api_key": None,
                "base_url": None,
                "working_dir": td,
                "approval_mode": "auto",
                "enable_planner": "false",
            }
        )
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/run", json={"prompt": "create hello.py that prints hello and run it"})
            assert resp.status == 200
            data = await resp.json()
            outputs = data["outputs"]
            assert len(outputs) >= 1
            assert (Path(td) / "hello.py").exists()


@pytest.mark.asyncio
async def test_chat_streaming() -> None:
    """Engine /chat endpoint returns a valid SSE stream."""
    with tempfile.TemporaryDirectory() as td:
        app = create_app(
            {
                "provider": "mock",
                "model": "mock",
                "api_key": None,
                "base_url": None,
                "working_dir": td,
                "approval_mode": "auto",
                "enable_planner": "false",
            }
        )
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/chat", json={"prompt": "create hi.py"})
            assert resp.status == 200
            body = await resp.text()
            assert "data:" in body
            assert "[DONE]" in body


@pytest.mark.asyncio
async def test_plan_task() -> None:
    """Engine /plan endpoint returns a structured plan."""
    with tempfile.TemporaryDirectory() as td:
        app = create_app(
            {
                "provider": "mock",
                "model": "mock",
                "api_key": None,
                "base_url": None,
                "working_dir": td,
                "approval_mode": "auto",
                "enable_planner": "false",
            }
        )
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/plan", json={"prompt": "add tests for the utils module"})
            assert resp.status == 200
            data = await resp.json()
            assert "task_id" in data
            assert "steps" in data
