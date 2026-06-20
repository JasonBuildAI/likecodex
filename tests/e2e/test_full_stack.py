"""Full-stack integration tests: Python engine bridged by Rust server."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE_URL = "http://127.0.0.1:19090"
SERVER_URL = "http://127.0.0.1:18080"


def _rust_server_available() -> bool:
    if shutil.which("cargo") is None:
        return False
    try:
        result = subprocess.run(
            ["cargo", "build", "-q", "-p", "likecodex-server"],
            cwd=ROOT,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _wait_for_health(client: httpx.Client, url: str, attempts: int = 40) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            resp = client.get(f"{url}/health", timeout=2.0)
            if resp.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001 - polling helper
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"health check failed for {url}: {last_error}")


@pytest.fixture(scope="module")
def full_stack():
    if os.environ.get("LIKECODEX_SKIP_INTEGRATION", "").lower() in {"1", "true", "yes"}:
        pytest.skip("LIKECODEX_SKIP_INTEGRATION is set")
    if not _rust_server_available():
        pytest.skip("Rust server unavailable (cargo build -p likecodex-server failed)")

    env = os.environ.copy()
    env.update(
        {
            "LIKECODEX_LLM_PROVIDER": "mock",
            "LIKECODEX_LLM_MODEL": "mock",
            "LIKECODEX_ENGINE_HOST": "127.0.0.1",
            "LIKECODEX_ENGINE_PORT": "19090",
            "LIKECODEX_ENGINE_URL": ENGINE_URL,
            "LIKECODEX_SERVER_HOST": "127.0.0.1",
            "LIKECODEX_SERVER_PORT": "18080",
            "LIKECODEX_APPROVAL_MODE": "auto",
        }
    )

    engine = subprocess.Popen(
        [sys.executable, "-m", "likecodex_engine.server"],
        cwd=ROOT,
        env=env,
    )
    server = subprocess.Popen(
        ["cargo", "run", "-q", "-p", "likecodex-server"],
        cwd=ROOT,
        env=env,
    )

    with httpx.Client() as client:
        try:
            _wait_for_health(client, ENGINE_URL)
            _wait_for_health(client, SERVER_URL)
            yield client
        finally:
            for proc in (server, engine):
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()


@pytest.mark.integration
def test_engine_health(full_stack: httpx.Client) -> None:
    resp = full_stack.get(f"{ENGINE_URL}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.integration
def test_server_health(full_stack: httpx.Client) -> None:
    resp = full_stack.get(f"{SERVER_URL}/health")
    assert resp.status_code == 200
    assert resp.text.strip() == "ok"


@pytest.mark.integration
def test_server_creates_task(full_stack: httpx.Client) -> None:
    resp = full_stack.post(
        f"{SERVER_URL}/tasks",
        json={"prompt": "say hello", "no_tools": True},
        timeout=10.0,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["task"]["id"]
    assert body["task"]["prompt"] == "say hello"


@pytest.mark.integration
def test_server_proxy_run(full_stack: httpx.Client) -> None:
    resp = full_stack.post(
        f"{SERVER_URL}/run",
        json={"prompt": "say hi"},
        timeout=30.0,
    )
    assert resp.status_code == 200
    outputs = resp.json()["outputs"]
    assert isinstance(outputs, list)
    assert outputs


@pytest.mark.integration
def test_server_sse_events(full_stack: httpx.Client) -> None:
    full_stack.post(
        f"{SERVER_URL}/tasks",
        json={"prompt": "quick task", "no_tools": True},
        timeout=10.0,
    )
    time.sleep(1.5)

    event_types: list[str] = []
    with full_stack.stream("GET", f"{SERVER_URL}/events", timeout=20.0) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line.removeprefix("data:").strip()
            if payload == "[DONE]":
                break
            parsed = json.loads(payload)
            event_type = parsed.get("type")
            if event_type:
                event_types.append(event_type)
            if "task_completed" in event_types:
                break

    assert "task_started" in event_types
    assert "stream_chunk" in event_types or "task_completed" in event_types


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("LIKECODEX_RUN_SANDBOX_TESTS", "").lower() not in {"1", "true", "yes"},
    reason="Set LIKECODEX_RUN_SANDBOX_TESTS=1 and ensure Docker sandbox image is built",
)
def test_sandbox_execute_endpoint(full_stack: httpx.Client) -> None:
    resp = full_stack.post(
        f"{SERVER_URL}/execute",
        json={"command": "echo sandbox-ok"},
        timeout=60.0,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("exit_code") == 0
    assert "sandbox-ok" in str(body.get("stdout", ""))
