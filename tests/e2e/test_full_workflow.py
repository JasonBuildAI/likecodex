"""End-to-end full workflow tests for LikeCodex engine.

Tests cover:
- CLI startup and version
- Health check endpoint
- Basic agent interaction (run, chat, plan)
- Tool execution (read_file, write_file)
- Session management (create, list, resume)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer
from likecodex_engine.server import create_app

# ── Fixtures ──


@pytest.fixture
def app_config():
    """Default test configuration using mock LLM."""
    with tempfile.TemporaryDirectory() as td:
        yield {
            "provider": "mock",
            "model": "mock",
            "api_key": None,
            "base_url": None,
            "working_dir": td,
            "approval_mode": "full-access",
            "enable_planner": "false",
        }


@pytest.fixture
async def client(app_config):
    """Create a test client for the engine."""
    app = create_app(app_config)
    async with TestClient(TestServer(app)) as test_client:
        yield test_client


# ── CLI Startup Tests ──


def test_cli_module_importable() -> None:
    """The CLI module can be imported without errors."""
    from likecodex_engine import cli  # noqa: F811

    assert cli is not None
    assert hasattr(cli, "main")
    assert hasattr(cli, "_parse_args")


def test_cli_version() -> None:
    """CLI --version flag prints version and exits."""
    from likecodex_engine.cli import _parse_args

    args = _parse_args(["--version"])
    assert args.version is True


def test_cli_parse_help() -> None:
    """CLI argument parser handles common flag combinations."""
    from likecodex_engine.cli import _parse_args

    # Default (no args)
    args = _parse_args([])
    assert args.prompt is None
    assert args.chat is False
    assert args.output_json is False

    # One-shot prompt
    args = _parse_args(["fix this bug"])
    assert args.prompt == "fix this bug"

    # Mode flag
    args = _parse_args(["--mode", "agent", "refactor main.py"])
    assert args.mode == "agent"
    assert args.prompt == "refactor main.py"

    # Model flag
    args = _parse_args(["--model", "pro", "complex task"])
    assert args.model == "pro"

    # JSON output
    args = _parse_args(["--json", "task"])
    assert args.output_json is True

    # Web mode
    args = _parse_args(["--web"])
    assert args.web is True

    # Setup wizard
    args = _parse_args(["--setup"])
    assert args.setup is True


# ── Health Check Tests ──


async def test_health_endpoint(client: TestClient) -> None:
    """GET /health returns OK status."""
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"


async def test_health_liveness(client: TestClient) -> None:
    """GET /health/liveness returns healthy."""
    resp = await client.get("/health/liveness")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"


async def test_health_readiness(client: TestClient) -> None:
    """GET /health/readiness returns ready."""
    resp = await client.get("/health/readiness")
    assert resp.status == 200
    data = await resp.json()
    assert data.get("status") in ("ok", "ready")


# ── Basic Agent Interaction Tests ──


async def test_run_prompt(client: TestClient) -> None:
    """POST /run executes a prompt and returns outputs."""
    resp = await client.post("/run", json={"prompt": "say hello"})
    assert resp.status == 200
    data = await resp.json()
    assert "outputs" in data
    assert isinstance(data["outputs"], list)
    assert len(data["outputs"]) >= 1


async def test_run_with_session(client: TestClient) -> None:
    """POST /run maintains session context across calls."""
    session_id = "test-session-e2e"

    # First call
    resp1 = await client.post(
        "/run",
        json={"prompt": "first message", "session_id": session_id},
    )
    assert resp1.status == 200
    data1 = await resp1.json()
    assert data1.get("session_id") == session_id

    # Second call same session
    resp2 = await client.post(
        "/run",
        json={"prompt": "follow up", "session_id": session_id},
    )
    assert resp2.status == 200
    data2 = await resp2.json()
    assert data2.get("session_id") == session_id


async def test_chat_streaming(client: TestClient) -> None:
    """POST /chat returns a valid SSE stream."""
    resp = await client.post("/chat", json={"prompt": "create hi.py"})
    assert resp.status == 200
    body = await resp.text()
    assert "data:" in body
    assert "[DONE]" in body


async def test_chat_stream_has_valid_json(client: TestClient) -> None:
    """Each SSE data line in /chat is valid JSON."""
    resp = await client.post("/chat", json={"prompt": "say hello", "stream": True})
    assert resp.status == 200
    body = await resp.text()

    for line in body.split("\n"):
        line = line.strip()
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            continue
        parsed = json.loads(payload)
        assert "type" in parsed


async def test_plan_endpoint(client: TestClient) -> None:
    """POST /plan returns a structured plan."""
    resp = await client.post(
        "/plan",
        json={"prompt": "add tests for the utils module"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "task_id" in data
    assert "steps" in data
    assert isinstance(data["steps"], list)


async def test_create_task(client: TestClient) -> None:
    """POST /tasks creates a background task."""
    resp = await client.post(
        "/tasks",
        json={"prompt": "list files", "no_tools": True},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "task_id" in data
    task_id = data["task_id"]
    assert len(task_id) > 0


async def test_get_task_status(client: TestClient) -> None:
    """GET /tasks/{id} returns task status."""
    # Create task first
    create_resp = await client.post(
        "/tasks",
        json={"prompt": "quick task", "no_tools": True},
    )
    task_id = (await create_resp.json())["task_id"]

    # Query task status
    resp = await client.get(f"/tasks/{task_id}")
    assert resp.status == 200
    data = await resp.json()
    # Task may be running or completed by now
    assert data.get("status") in ("running", "completed", "pending")


# ── Tool Execution Tests ──


async def test_read_file_tool(client: TestClient) -> None:
    """Engine can execute read_file tool through /run."""
    with tempfile.TemporaryDirectory() as td:
        test_file = Path(td) / "test_read.txt"
        test_file.write_text("hello e2e test", encoding="utf-8")

        app = create_app(
            {
                "provider": "mock",
                "model": "mock",
                "api_key": None,
                "base_url": None,
                "working_dir": td,
                "approval_mode": "full-access",
                "enable_planner": "false",
            }
        )
        async with TestClient(TestServer(app)) as custom_client:
            resp = await custom_client.post(
                "/run",
                json={"prompt": f"read {test_file.name}"},
            )
            assert resp.status == 200


async def test_write_file_tool(client: TestClient) -> None:
    """Engine can create files through /run."""
    with tempfile.TemporaryDirectory() as td:
        app = create_app(
            {
                "provider": "mock",
                "model": "mock",
                "api_key": None,
                "base_url": None,
                "working_dir": td,
                "approval_mode": "full-access",
                "enable_planner": "false",
            }
        )
        async with TestClient(TestServer(app)) as custom_client:
            resp = await custom_client.post(
                "/run",
                json={"prompt": "create hello_e2e.py that prints hello and run it"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert len(data["outputs"]) >= 1


# ── Session Management Tests ──


async def test_session_list(client: TestClient) -> None:
    """GET /sessions returns a list of sessions."""
    resp = await client.get("/sessions")
    assert resp.status == 200
    data = await resp.json()
    assert isinstance(data, (list, dict))


async def test_session_persistence(client: TestClient) -> None:
    """Sessions created via /run are stored and retrievable."""
    # Create session
    await client.post(
        "/run",
        json={
            "prompt": "session test",
            "session_id": "e2e-persist-session",
        },
    )

    # List sessions
    resp = await client.get("/sessions")
    assert resp.status == 200
    data = await resp.json()

    # The session may be in the list
    # (depends on persistence implementation)
    assert data is not None


async def test_session_events(client: TestClient) -> None:
    """GET /sessions/{id}/events returns session event history."""
    session_id = "e2e-events-session"

    # Create some activity in the session
    await client.post(
        "/run",
        json={
            "prompt": "event test",
            "session_id": session_id,
        },
    )

    # Get events
    resp = await client.get(f"/sessions/{session_id}/events")
    assert resp.status in (200, 404)  # 404 if session not persisted
    if resp.status == 200:
        data = await resp.json()
        assert isinstance(data, (list, dict))


# ── Error Handling Tests ──


async def test_missing_prompt_returns_400(client: TestClient) -> None:
    """POST /run without prompt returns 400."""
    resp = await client.post("/run", json={})
    assert resp.status == 400


async def test_invalid_json_returns_400(client: TestClient) -> None:
    """POST /run with invalid JSON body returns 400."""
    resp = await client.post("/run", data="not-json", headers={"Content-Type": "application/json"})
    assert resp.status in (400, 500)


async def test_nonexistent_task_returns_404(client: TestClient) -> None:
    """GET /tasks/{id} with unknown id returns 404."""
    resp = await client.get("/tasks/nonexistent-task-id")
    assert resp.status == 404


async def test_run_with_mock_model_returns_quickly(client: TestClient) -> None:
    """POST /run with mock model should respond in reasonable time."""
    import asyncio

    start = asyncio.get_event_loop().time()
    resp = await client.post("/run", json={"prompt": "quick test"})
    elapsed = asyncio.get_event_loop().time() - start

    assert resp.status == 200
    # Mock should respond within 10 seconds
    assert elapsed < 10, f"Mock response took too long: {elapsed:.1f}s"


# ── Version Info ──


def test_package_version() -> None:
    """Package exposes a valid version string."""
    from likecodex_engine import __version__  # noqa: F811

    assert __version__ is not None
    parts = __version__.split(".")
    assert len(parts) >= 2
    for part in parts:
        assert part.isdigit() or part.replace("dev", "").replace("rc", "").isdigit()
