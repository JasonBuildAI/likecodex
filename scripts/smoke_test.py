#!/usr/bin/env python3
"""Smoke-test script for CI: engine + server health, task creation, and SSE events."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_URL = os.environ.get("LIKECODEX_ENGINE_URL", "http://127.0.0.1:9090")
SERVER_URL = os.environ.get("LIKECODEX_SERVER_URL", "http://127.0.0.1:8080")
ENGINE_PORT = os.environ.get("LIKECODEX_ENGINE_PORT", "9090")
SERVER_PORT = os.environ.get("LIKECODEX_SERVER_PORT", "8080")


def http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def http_post_json(url: str, payload: dict, timeout: float = 10.0) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def wait_for_health(url: str, label: str, attempts: int = 30) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            status, body = http_get(f"{url}/health")
            if status == 200 and "ok" in body.lower():
                print(f"[ok] {label} healthy at {url}")
                return
        except Exception as exc:  # noqa: BLE001 - smoke script
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"{label} failed health check at {url}: {last_error}")


def read_sse_events(url: str, timeout_secs: float = 15.0) -> list[str]:
    req = urllib.request.Request(url, method="GET", headers={"Accept": "text/event-stream"})
    events: list[str] = []
    deadline = time.time() + timeout_secs
    with urllib.request.urlopen(req, timeout=timeout_secs + 5) as resp:
        while time.time() < deadline:
            line = resp.readline().decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            payload = line.removeprefix("data:").strip()
            if payload == "[DONE]":
                break
            try:
                parsed = json.loads(payload)
                event_type = parsed.get("type")
                if event_type:
                    events.append(str(event_type))
            except json.JSONDecodeError:
                continue
            if "task_completed" in events and "stream_finished" in events:
                break
    return events


def main() -> int:
    env = os.environ.copy()
    env.setdefault("LIKECODEX_LLM_PROVIDER", "mock")
    env.setdefault("LIKECODEX_LLM_MODEL", "mock")
    env.setdefault("LIKECODEX_ENGINE_HOST", "127.0.0.1")
    env.setdefault("LIKECODEX_ENGINE_PORT", ENGINE_PORT)
    env.setdefault("LIKECODEX_ENGINE_URL", ENGINE_URL)
    env.setdefault("LIKECODEX_SERVER_HOST", "127.0.0.1")
    env.setdefault("LIKECODEX_SERVER_PORT", SERVER_PORT)

    engine_proc = subprocess.Popen(
        [sys.executable, "-m", "likecodex_engine.server"],
        cwd=ROOT,
        env=env,
    )
    server_proc = subprocess.Popen(
        ["cargo", "run", "-q", "-p", "likecodex-server"],
        cwd=ROOT,
        env=env,
    )

    try:
        wait_for_health(ENGINE_URL, "engine")
        wait_for_health(SERVER_URL, "server")

        status, body = http_post_json(
            f"{SERVER_URL}/tasks",
            {"prompt": "list files in the workspace", "no_tools": True},
        )
        if status != 200:
            raise RuntimeError(f"POST /tasks failed: {status} {body}")
        task = json.loads(body).get("task") or {}
        task_id = task.get("id")
        if not task_id:
            raise RuntimeError(f"POST /tasks missing task id: {body}")

        # Allow background task to emit events.
        time.sleep(2)
        events = read_sse_events(f"{SERVER_URL}/events")
        required = {"task_started", "stream_chunk", "task_completed"}
        missing = required - set(events)
        if missing:
            raise RuntimeError(f"SSE missing events {sorted(missing)}; saw {events}")

        print(f"[ok] smoke passed task_id={task_id} events={events}")
        return 0
    finally:
        for proc in (server_proc, engine_proc):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print(f"[fail] smoke test network error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
