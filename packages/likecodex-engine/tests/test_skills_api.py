"""Tests for Skills API endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from likecodex_engine.server import create_app


def _app(working_dir: str) -> "web.Application":
    return create_app(
        {
            "provider": "mock",
            "model": "mock",
            "api_key": None,
            "base_url": None,
            "working_dir": working_dir,
            "approval_mode": "auto",
        }
    )


@pytest.mark.asyncio
async def test_skills_list() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/ide/skills/list")
            assert resp.status == 200
            data = await resp.json()
            assert "skills" in data
            # Should include built-in skills
            assert len(data["skills"]) > 0
            # Each skill should have full metadata
            skill = data["skills"][0]
            assert "name" in skill
            assert "description" in skill
            assert "source" in skill
            assert "enabled" in skill


@pytest.mark.asyncio
async def test_skills_detail() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            # Get list first
            resp = await client.get("/api/ide/skills/list")
            data = await resp.json()
            assert len(data["skills"]) > 0
            name = data["skills"][0]["name"]
            # Get detail
            resp = await client.get(f"/api/ide/skills/detail?name={name}")
            assert resp.status == 200
            detail = await resp.json()
            assert detail["name"] == name
            assert "body" in detail

    # Test missing name
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/ide/skills/detail")
            assert resp.status == 400

    # Test non-existent
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/ide/skills/detail?name=nonexistent")
            assert resp.status == 404


@pytest.mark.asyncio
async def test_skills_create() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/ide/skills/create",
                json={
                    "name": "test-api-skill",
                    "description": "Created via API",
                    "body": "Do something.",
                },
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            assert data["skill"]["name"] == "test-api-skill"

    # Test invalid name
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/ide/skills/create",
                json={"name": "INVALID NAME!", "description": "bad"},
            )
            assert resp.status == 400


@pytest.mark.asyncio
async def test_skills_update() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            # Create first
            await client.post(
                "/api/ide/skills/create",
                json={"name": "upd-api-skill", "description": "Old"},
            )
            # Update
            resp = await client.put(
                "/api/ide/skills/update",
                json={"name": "upd-api-skill", "description": "New desc"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            assert "New desc" in str(data.get("skill", {}).get("description", ""))


@pytest.mark.asyncio
async def test_skills_delete() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            # Create
            await client.post(
                "/api/ide/skills/create",
                json={"name": "del-api-skill", "description": "Delete me"},
            )
            # Delete
            resp = await client.delete(
                "/api/ide/skills/delete",
                json={"name": "del-api-skill"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True

            # Verify gone
            resp = await client.get("/api/ide/skills/detail?name=del-api-skill")
            assert resp.status == 404


@pytest.mark.asyncio
async def test_skills_enable_toggle() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            # Create
            await client.post(
                "/api/ide/skills/create",
                json={"name": "tog-skill", "description": "Toggle me"},
            )
            # Toggle (should disable, since it starts enabled)
            resp = await client.post(
                "/api/ide/skills/enable",
                json={"name": "tog-skill"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["enabled"] is False

            # Toggle again (should re-enable)
            resp = await client.post(
                "/api/ide/skills/enable",
                json={"name": "tog-skill"},
            )
            data = await resp.json()
            assert data["enabled"] is True


@pytest.mark.asyncio
async def test_skills_reload() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/ide/skills/reload")
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            assert "skills_count" in data
            assert "skills" in data


@pytest.mark.asyncio
async def test_skills_invoke_inline() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            # Create an inline skill
            await client.post(
                "/api/ide/skills/create",
                json={"name": "inv-skill", "description": "Invoke me", "body": "Skill body text"},
            )
            # Invoke
            resp = await client.post(
                "/api/ide/skills/invoke",
                json={"name": "inv-skill"},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["skill"] == "inv-skill"
            assert data["mode"] == "inline"
            assert "Skill body text" in data["body"]


@pytest.mark.asyncio
async def test_skills_invoke_not_found() -> None:
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/ide/skills/invoke",
                json={"name": "nonexistent"},
            )
            assert resp.status == 404


@pytest.mark.asyncio
async def test_old_skills_endpoint_still_works() -> None:
    """Verify the original GET /skills endpoint still works."""
    with tempfile.TemporaryDirectory() as td:
        app = _app(td)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/skills")
            assert resp.status == 200
            data = await resp.json()
            assert "skills" in data
