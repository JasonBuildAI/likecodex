"""E2E tests for Skills + MCP integration.

Tests:
- Skill CRUD (create, read, update, delete)
- Skill marketplace install/export/import
- MCP tool listing
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE_URL = "http://127.0.0.1:19090"
SERVER_URL = "http://127.0.0.1:18080"

pytestmark = pytest.mark.skipif(
    os.environ.get("LIKECODEX_SKIP_INTEGRATION", "").lower() in {"1", "true", "yes"},
    reason="LIKECODEX_SKIP_INTEGRATION is set",
)


class SkillsE2ETestBase:
    """Base class with shared helpers for skills E2E tests."""

    @pytest.fixture(scope="module")
    def engine_client(self) -> httpx.Client:
        """Create an HTTP client pointing to the engine."""
        client = httpx.Client(base_url=ENGINE_URL, timeout=10)
        try:
            resp = client.get("/health")
            assert resp.status_code == 200, "Engine not running"
        except (httpx.ConnectError, AssertionError):
            pytest.skip("Engine is not running (start with: uv run likecodex-engine)")
        return client

    def _create_skill_payload(self, name: str, **overrides: Any) -> dict:
        return {
            "name": name,
            "description": overrides.get("description", f"Test skill {name}"),
            "body": overrides.get("body", f"# {name}\n\nThis is a test skill."),
            "run_as": overrides.get("run_as", "inline"),
            "model": overrides.get("model"),
            "allowed_tools": overrides.get("allowed_tools", []),
            "author": overrides.get("author", "e2e-test"),
            "version": overrides.get("version", "0.1.0"),
        }


class TestSkillsCRUD(SkillsE2ETestBase):
    """E2E tests for skill create, read, update, and delete."""

    def test_skills_list_empty(self, engine_client: httpx.Client) -> None:
        """Listing skills should return a list (possibly empty)."""
        resp = engine_client.get("/api/ide/skills/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert isinstance(data["skills"], list)

    def test_skills_create_and_detail(self, engine_client: httpx.Client) -> None:
        """Create a skill and verify it appears in detail view."""
        skill_name = "e2e-test-create-1"
        payload = self._create_skill_payload(skill_name, description="E2E create test")

        resp = engine_client.post("/api/ide/skills/create", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True, f"Create failed: {data}"

        # Verify in detail
        resp = engine_client.get(f"/api/ide/skills/detail?name={skill_name}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail.get("name") == skill_name
        assert detail.get("description") == "E2E create test"

        # Clean up
        engine_client.delete("/api/ide/skills/delete", json={"name": skill_name})

    def test_skills_update(self, engine_client: httpx.Client) -> None:
        """Create a skill, update it, and verify changes."""
        skill_name = "e2e-test-update-1"
        # Create
        engine_client.post("/api/ide/skills/create", json=self._create_skill_payload(skill_name))
        # Update
        resp = engine_client.put("/api/ide/skills/update", json={
            "name": skill_name,
            "description": "Updated description",
            "body": "# Updated\nChanged body",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

        # Verify
        resp = engine_client.get(f"/api/ide/skills/detail?name={skill_name}")
        detail = resp.json()
        assert detail.get("description") == "Updated description"

        # Clean up
        engine_client.delete("/api/ide/skills/delete", json={"name": skill_name})

    def test_skills_delete(self, engine_client: httpx.Client) -> None:
        """Create and delete a skill."""
        skill_name = "e2e-test-delete-1"
        engine_client.post("/api/ide/skills/create", json=self._create_skill_payload(skill_name))

        resp = engine_client.delete("/api/ide/skills/delete", json={"name": skill_name})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

        # Verify it's gone
        resp = engine_client.get(f"/api/ide/skills/detail?name={skill_name}")
        assert resp.status_code == 404

    def test_skills_toggle_enable(self, engine_client: httpx.Client) -> None:
        """Toggle skill enabled/disabled state."""
        skill_name = "e2e-test-toggle-1"
        engine_client.post("/api/ide/skills/create", json=self._create_skill_payload(skill_name))

        # Toggle (disable)
        resp = engine_client.post("/api/ide/skills/enable", json={"name": skill_name})
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data

        # Toggle again (enable)
        resp = engine_client.post("/api/ide/skills/enable", json={"name": skill_name})
        assert resp.status_code == 200

        # Clean up
        engine_client.delete("/api/ide/skills/delete", json={"name": skill_name})


class TestSkillsExportImport(SkillsE2ETestBase):
    """E2E tests for skill export and import."""

    def test_skills_export(self, engine_client: httpx.Client) -> None:
        """Create a skill and export it as zip."""
        skill_name = "e2e-test-export-1"
        engine_client.post("/api/ide/skills/create", json=self._create_skill_payload(skill_name))

        resp = engine_client.get(f"/api/ide/skills/export?name={skill_name}")
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/zip"

        # Verify it's a valid zip
        zip_data = resp.content
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            names = zf.namelist()
            assert len(names) > 0

        # Clean up
        engine_client.delete("/api/ide/skills/delete", json={"name": skill_name})

    def test_skills_import(self, engine_client: httpx.Client) -> None:
        """Export a skill, delete it, then import it back."""
        skill_name = "e2e-test-import-1"
        engine_client.post("/api/ide/skills/create", json=self._create_skill_payload(skill_name))

        # Export
        resp = engine_client.get(f"/api/ide/skills/export?name={skill_name}")
        assert resp.status_code == 200
        zip_data = resp.content

        # Delete original
        engine_client.delete("/api/ide/skills/delete", json={"name": skill_name})

        # Import back
        resp = engine_client.post(
            "/api/ide/skills/import",
            files={"file": ("skills.zip", zip_data, "application/zip")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

        # Verify it exists
        resp = engine_client.get(f"/api/ide/skills/detail?name={skill_name}")
        assert resp.status_code == 200

        # Clean up
        engine_client.delete("/api/ide/skills/delete", json={"name": skill_name})


class TestMCPListing(SkillsE2ETestBase):
    """E2E tests for MCP tool listing."""

    def test_mcp_servers_list(self, engine_client: httpx.Client) -> None:
        """List MCP servers should return a list."""
        resp = engine_client.get("/api/ide/mcp/servers")
        assert resp.status_code == 200
        data = resp.json()
        assert "servers" in data
        assert isinstance(data["servers"], list)

    def test_mcp_tools_list(self, engine_client: httpx.Client) -> None:
        """List MCP tools should return tools."""
        resp = engine_client.get("/api/ide/mcp/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "per_server" in data

    def test_mcp_server_status(self, engine_client: httpx.Client) -> None:
        """Get status of a specific server."""
        # Try a server that doesn't exist
        resp = engine_client.get("/api/ide/mcp/status?name=nonexistent")
        # Should return error or a valid response
        assert resp.status_code in (200, 400)


class TestSkillsMarketplace(SkillsE2ETestBase):
    """E2E tests for skills marketplace."""

    def test_marketplace_list(self, engine_client: httpx.Client) -> None:
        """Browse the marketplace."""
        resp = engine_client.get("/api/ide/skills/marketplace")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data

    def test_marketplace_search(self, engine_client: httpx.Client) -> None:
        """Search the marketplace."""
        resp = engine_client.get("/api/ide/skills/marketplace?q=test")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
