"""Tests for SessionShareService and HTTP API."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from likecodex_engine.tools.session_share import SessionShareTools


class TestSessionShareService:
    """Tests for SessionShareService core functionality."""

    @pytest.mark.asyncio
    async def test_share_json_format(self) -> None:
        tools = SessionShareTools()
        result = await tools.share("test-session-id", format="json")
        data = json.loads(result)
        assert "token" in data
        assert data["format"] == "json"
        assert data["expires_in"] == 86400

    @pytest.mark.asyncio
    async def test_share_with_custom_expiry(self) -> None:
        tools = SessionShareTools()
        result = await tools.share("test-session-id", format="markdown", expiry=3600)
        data = json.loads(result)
        assert data["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_share_link_format(self) -> None:
        tools = SessionShareTools()
        result = await tools.share("test-session-id", format="link")
        data = json.loads(result)
        assert data["url"].startswith("https://likecodex.app/share/")

    @pytest.mark.asyncio
    async def test_export_default_format(self) -> None:
        tools = SessionShareTools()
        result = await tools.export("session-123")
        data = json.loads(result)
        assert data["format"] == "json"

    @pytest.mark.asyncio
    async def test_export_markdown(self) -> None:
        tools = SessionShareTools()
        result = await tools.export("session-123", format="markdown")
        data = json.loads(result)
        assert data["format"] == "markdown"
        assert "Session:" in data["content"]

    @pytest.mark.asyncio
    async def test_export_html(self) -> None:
        tools = SessionShareTools()
        result = await tools.export("session-123", format="html")
        data = json.loads(result)
        assert data["format"] == "html"
        assert "<html>" in data["content"]

    @pytest.mark.asyncio
    async def test_import_valid_data(self) -> None:
        tools = SessionShareTools()
        data = json.dumps({
            "session_id": "imported-session",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ],
        })
        result = await tools.import_(data)
        parsed = json.loads(result)
        assert parsed["status"] == "imported"
        assert parsed["messages_count"] == 2

    @pytest.mark.asyncio
    async def test_import_empty_messages(self) -> None:
        tools = SessionShareTools()
        data = json.dumps({"session_id": "empty"})
        result = await tools.import_(data)
        parsed = json.loads(result)
        assert parsed["messages_count"] == 0

    @pytest.mark.asyncio
    async def test_share_error_handling(self) -> None:
        tools = SessionShareTools()
        # Passing an invalid session_id should still return a valid response
        result = await tools.share("test", format="markdown")
        data = json.loads(result)
        assert "content" in data

    @pytest.mark.asyncio
    async def test_export_error_handling(self) -> None:
        tools = SessionShareTools()
        result = await tools.export("test")
        data = json.loads(result)
        assert "content" in data


class TestSessionShareRender:
    """Tests for the _render static method."""

    def test_render_unknown_format(self) -> None:
        result = SessionShareTools._render("test", "unknown")
        assert result == ""

    def test_render_link(self) -> None:
        result = SessionShareTools._render("test", "link")
        assert result == "https://likecodex.app/share/test"
