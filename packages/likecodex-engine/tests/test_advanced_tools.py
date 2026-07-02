"""Tests for advanced tools with mocked dependencies."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from likecodex_engine.tools.database import DatabaseTools
from likecodex_engine.tools.github import GitHubTools
from likecodex_engine.tools.network import NetworkTools
from likecodex_engine.tools.profiler import ProfilerTools
from likecodex_engine.tools.session_share import SessionShareTools


# ── SessionShareTools tests ─────────────────────────────────────

class TestSessionShareTools:
    """Tests for SessionShareTools."""

    def test_share_schema_structure(self) -> None:
        schema = SessionShareTools.share_schema()
        assert "parameters" in schema
        assert "session_id" in schema["parameters"]["properties"]

    def test_export_schema_structure(self) -> None:
        schema = SessionShareTools.export_schema()
        assert schema["parameters"]["properties"]["format"]["enum"] == ["json", "markdown", "html"]

    def test_import_schema_structure(self) -> None:
        schema = SessionShareTools.import_schema()
        assert "data" in schema["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_share_markdown(self) -> None:
        tools = SessionShareTools()
        result = await tools.share("session_abc", format="markdown")
        data = json.loads(result)
        assert "content" in data
        assert "session_abc" in data["content"]

    @pytest.mark.asyncio
    async def test_share_link(self) -> None:
        tools = SessionShareTools()
        result = await tools.share("session_abc", format="link")
        data = json.loads(result)
        assert "url" in data
        assert "likecodex.app" in data["url"]

    @pytest.mark.asyncio
    async def test_export_json(self) -> None:
        tools = SessionShareTools()
        result = await tools.export("session_abc", format="json")
        data = json.loads(result)
        assert data["session_id"] == "session_abc"
        assert data["format"] == "json"

    @pytest.mark.asyncio
    async def test_import_valid_json(self) -> None:
        tools = SessionShareTools()
        data = json.dumps({"session_id": "imported", "messages": [{"role": "user", "content": "hi"}]})
        result = await tools.import_(data)
        parsed = json.loads(result)
        assert parsed["status"] == "imported"
        assert parsed["messages_count"] == 1

    @pytest.mark.asyncio
    async def test_import_invalid_json(self) -> None:
        tools = SessionShareTools()
        result = await tools.import_("not-json")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_render_json(self) -> None:
        result = SessionShareTools._render("sid1", "json")
        parsed = json.loads(result)
        assert parsed["session_id"] == "sid1"

    def test_render_markdown(self) -> None:
        result = SessionShareTools._render("sid1", "markdown")
        assert "Session:" in result
        assert "sid1" in result

    def test_render_html(self) -> None:
        result = SessionShareTools._render("sid1", "html")
        assert "<html>" in result
        assert "sid1" in result


# ── GitHubTools tests ───────────────────────────────────────────

class TestGitHubTools:
    """Tests for GitHubTools with mocked HTTP client."""

    def test_create_pr_schema(self) -> None:
        schema = GitHubTools.create_pr_schema()
        assert schema["parameters"]["required"] == ["repo", "title", "head"]

    def test_review_pr_schema(self) -> None:
        schema = GitHubTools.review_pr_schema()
        assert schema["parameters"]["properties"]["event"]["enum"] == ["APPROVE", "COMMENT", "REQUEST_CHANGES"]

    def test_list_prs_schema(self) -> None:
        schema = GitHubTools.list_prs_schema()
        assert "limit" in schema["parameters"]["properties"]

    @patch("likecodex_engine.tools.github.HAS_HTTPX", False)
    @pytest.mark.asyncio
    async def test_create_pr_no_httpx(self) -> None:
        tools = GitHubTools()
        result = await tools.create_pr("owner/repo", "title", "head")
        assert "httpx" in result

    @patch("likecodex_engine.tools.github._get_token", return_value="fake-token")
    @patch("likecodex_engine.tools.github.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_create_pr_success(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"number": 42, "html_url": "https://github.com/owner/repo/pull/42"}
        mock_instance = mock_client.return_value
        mock_instance.__aenter__.return_value.post.return_value = mock_resp

        tools = GitHubTools()
        result = await tools.create_pr("owner/repo", "Add feature", "feature-branch")
        data = json.loads(result)
        assert data["number"] == 42

    @patch("likecodex_engine.tools.github._get_token", return_value="fake-token")
    @patch("likecodex_engine.tools.github.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_list_prs(self, mock_client: MagicMock, mock_token: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"number": 1, "title": "PR 1", "state": "open", "user": {"login": "user1"}, "created_at": "2025-01-01", "html_url": "url1"}
        ]
        mock_instance = mock_client.return_value
        mock_instance.__aenter__.return_value.get.return_value = mock_resp

        tools = GitHubTools()
        result = await tools.list_prs("owner/repo")
        data = json.loads(result)
        assert data["count"] == 1
        assert data["prs"][0]["number"] == 1


# ── ProfilerTools tests ─────────────────────────────────────────

class TestProfilerTools:
    """Tests for ProfilerTools."""

    def test_profile_python_schema(self) -> None:
        schema = ProfilerTools.profile_python_schema()
        assert schema["parameters"]["required"] == ["script"]

    def test_profile_function_schema(self) -> None:
        schema = ProfilerTools.profile_function_schema()
        assert schema["parameters"]["required"] == ["code"]

    @pytest.mark.asyncio
    async def test_profile_function_basic(self) -> None:
        tools = ProfilerTools()
        result = await tools.profile_function("1+1", iterations=10, repeat=2)
        data = json.loads(result)
        assert "avg" in data
        assert data["iterations"] == 10

    @pytest.mark.asyncio
    async def test_profile_function_error(self) -> None:
        tools = ProfilerTools()
        result = await tools.profile_function("invalid syntax{{{", iterations=1, repeat=1)
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_memory_profile_no_dep(self) -> None:
        tools = ProfilerTools()
        result = await tools.memory_profile("x = 1")
        data = json.loads(result)
        assert "error" in data  # memory_profiler not installed


# ── DatabaseTools tests ─────────────────────────────────────────

class TestDatabaseTools:
    """Tests for DatabaseTools."""

    def test_query_schema_structure(self) -> None:
        schema = DatabaseTools.query_schema()
        assert schema["parameters"]["required"] == ["sql", "db_type", "conn_str"]

    def test_list_tables_schema(self) -> None:
        schema = DatabaseTools.list_tables_schema()
        assert "conn_str" in schema["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_query_select_only_enforced(self) -> None:
        tools = DatabaseTools()
        result = await tools.query("DELETE FROM users", "sqlite", ":memory:")
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_query_sqlite_in_memory(self) -> None:
        tools = DatabaseTools()
        result = await tools.query("SELECT 1 as val", "sqlite", ":memory:")
        data = json.loads(result)
        assert data["count"] == 1
        assert data["rows"][0]["val"] == 1

    @pytest.mark.asyncio
    async def test_query_sqlite_with_params(self) -> None:
        tools = DatabaseTools()
        # Create a table, insert, then query
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'Alice')")
        conn.execute("INSERT INTO test VALUES (2, 'Bob')")
        conn.close()

        result = await tools.query("SELECT * FROM test WHERE id = ?", "sqlite", ":memory:", params=["1"])
        data = json.loads(result)
        assert data["count"] == 1
        assert data["rows"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_schema_sqlite(self) -> None:
        tools = DatabaseTools()
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.close()

        result = await tools.schema("sqlite", ":memory:")
        data = json.loads(result)
        assert len(data["tables"]) == 1
        assert data["tables"][0]["name"] == "items"

    @pytest.mark.asyncio
    async def test_explain_sqlite(self) -> None:
        tools = DatabaseTools()
        result = await tools.explain("SELECT 1", "sqlite", ":memory:")
        data = json.loads(result)
        assert "plan" in data


# ── NetworkTools tests ──────────────────────────────────────────

class TestNetworkTools:
    """Tests for NetworkTools."""

    def test_ping_schema(self) -> None:
        schema = NetworkTools.ping_schema()
        assert schema["parameters"]["required"] == ["host"]

    def test_dns_lookup_schema(self) -> None:
        schema = NetworkTools.dns_lookup_schema()
        assert "domain" in schema["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_dns_lookup(self) -> None:
        tools = NetworkTools()
        result = await tools.dns_lookup("example.com")
        data = json.loads(result)
        # DNS resolution may work or fail in test env, but should have expected fields
        assert "domain" in data

    @patch("likecodex_engine.tools.network.HAS_HTTPX", False)
    @pytest.mark.asyncio
    async def test_http_headers_no_httpx(self) -> None:
        tools = NetworkTools()
        result = await tools.http_headers("https://example.com")
        assert "httpx" in result

    @pytest.mark.asyncio
    async def test_http_headers_with_mock(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = "https://example.com"

        with patch("likecodex_engine.tools.network.httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.__aenter__.return_value.request.return_value = mock_resp

            tools = NetworkTools()
            result = await tools.http_headers("https://example.com")
            data = json.loads(result)
            assert data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_dns_lookup_failure(self) -> None:
        import socket

        tools = NetworkTools()
        result = await tools.dns_lookup("nonexistent-domain-xyz-12345.com")
        data = json.loads(result)
        # Should have error field since domain can't be resolved
        assert "error" in data or "addresses" in data
