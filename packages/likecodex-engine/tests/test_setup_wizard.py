"""Tests for the SetupWizard configuration wizard."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from likecodex_engine.setup_wizard import (
    _mask_api_key,
    _render_config_toml,
    _step_api_key,
    _step_agent_mode,
    _step_optional_components,
    _step_provider_selection,
    _test_api_connectivity,
    interactive_setup,
    run_setup_wizard,
)


class TestRenderConfig:
    """Tests for config rendering utilities."""

    def test_render_config_toml_basic(self) -> None:
        config = {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-test123",
            "approval_mode": "auto",
            "online": True,
            "enable_planner": True,
            "optional_components": [],
        }
        toml = _render_config_toml(config)
        assert "[llm]" in toml
        assert 'provider = "deepseek"' in toml
        assert 'api_key = "sk-test123"' in toml
        assert "[approval]" in toml
        assert 'mode = "auto"' in toml

    def test_render_config_toml_with_components(self) -> None:
        config = {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "",
            "approval_mode": "manual",
            "online": True,
            "enable_planner": False,
            "optional_components": ["sandbox", "webui"],
        }
        toml = _render_config_toml(config)
        assert "[install]" in toml
        assert "sandbox = true" in toml
        assert "webui = true" in toml

    def test_mask_api_key(self) -> None:
        content = 'api_key = "sk-real-key-12345"'
        masked = _mask_api_key(content, "sk-real-key-12345")
        assert "***" in masked
        assert "sk-real-key-12345" not in masked

    def test_mask_api_key_no_key(self) -> None:
        content = "some config without key"
        masked = _mask_api_key(content, "")
        assert masked == content

    def test_render_config_offline(self) -> None:
        config = {
            "provider": "offline-mock",
            "model": "mock-model",
            "base_url": "",
            "api_key": "",
            "approval_mode": "auto",
            "online": False,
            "enable_planner": True,
            "optional_components": [],
        }
        toml = _render_config_toml(config)
        assert 'provider = "offline-mock"' in toml
        # No api_key line when empty
        assert 'api_key = ""' not in toml


class TestStepProviderSelection:
    """Tests for provider selection step."""

    @patch("likecodex_engine.setup_wizard.console")
    @patch("likecodex_engine.setup_wizard.Prompt.ask", return_value="1")
    @pytest.mark.asyncio
    async def test_select_deepseek(self, mock_prompt: MagicMock, mock_console: MagicMock) -> None:
        config = await _step_provider_selection()
        assert config is not None
        assert config["provider"] == "deepseek"
        assert config["model"] == "deepseek-v4-flash"
        assert config["online"] is True

    @patch("likecodex_engine.setup_wizard.console")
    @patch("likecodex_engine.setup_wizard.Prompt.ask", return_value="3")
    @pytest.mark.asyncio
    async def test_select_offline(self, mock_prompt: MagicMock, mock_console: MagicMock) -> None:
        config = await _step_provider_selection()
        assert config is not None
        assert config["provider"] == "offline-mock"
        assert config["online"] is False
        assert config["base_url"] == ""


class TestStepApiKey:
    """Tests for API key collection step."""

    @patch("likecodex_engine.setup_wizard.console")
    @patch("likecodex_engine.setup_wizard.Prompt.ask", return_value="sk-test-key")
    @pytest.mark.asyncio
    async def test_api_key_provided(self, mock_prompt: MagicMock, mock_console: MagicMock) -> None:
        config = {"provider_name": "DeepSeek"}
        await _step_api_key(config)
        assert config["api_key"] == "sk-test-key"

    @patch("likecodex_engine.setup_wizard.console")
    @patch("likecodex_engine.setup_wizard.Prompt.ask", return_value="")
    @pytest.mark.asyncio
    async def test_api_key_empty(self, mock_prompt: MagicMock, mock_console: MagicMock) -> None:
        config = {"provider_name": "DeepSeek"}
        await _step_api_key(config)
        assert config["api_key"] == ""


class TestStepAgentMode:
    """Tests for agent mode selection step."""

    @patch("likecodex_engine.setup_wizard.console")
    @patch("likecodex_engine.setup_wizard.Prompt.ask", return_value="1")
    @patch("likecodex_engine.setup_wizard.Confirm.ask", return_value=True)
    @pytest.mark.asyncio
    async def test_auto_mode_with_planner(
        self, mock_confirm: MagicMock, mock_prompt: MagicMock, mock_console: MagicMock
    ) -> None:
        config: dict = {}
        await _step_agent_mode(config)
        assert config["approval_mode"] == "auto"
        assert config["enable_planner"] is True


class TestStepOptionalComponents:
    """Tests for optional components selection step."""

    @patch("likecodex_engine.setup_wizard.console")
    @patch("likecodex_engine.setup_wizard.Confirm.ask", side_effect=[True, False, True])
    @pytest.mark.asyncio
    async def test_select_some_components(
        self, mock_confirm: MagicMock, mock_console: MagicMock
    ) -> None:
        config: dict = {}
        await _step_optional_components(config)
        assert "sandbox" in config["optional_components"]
        assert "memory" not in config["optional_components"]
        assert "webui" in config["optional_components"]


class TestApiConnectivity:
    """Tests for API connectivity checking."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_false(self) -> None:
        result = await _test_api_connectivity("deepseek", "", "https://api.deepseek.com")
        assert result is False

    @patch("likecodex_engine.setup_wizard.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_deepseek_connectivity_ok(self, mock_openai: MagicMock) -> None:
        mock_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await _test_api_connectivity(
            "deepseek", "sk-test", "https://api.deepseek.com", "deepseek-v4-flash"
        )
        assert result is True

    @patch("likecodex_engine.setup_wizard.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_deepseek_connectivity_fail(self, mock_openai: MagicMock) -> None:
        mock_instance = mock_openai.return_value
        mock_instance.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await _test_api_connectivity(
            "deepseek", "sk-test", "https://api.deepseek.com"
        )
        assert result is False


class TestInteractiveSetup:
    """Tests for the full interactive setup wizard."""

    @patch("likecodex_engine.setup_wizard.run_setup_wizard", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_interactive_setup_alias(self, mock_wizard: AsyncMock) -> None:
        await interactive_setup()
        mock_wizard.assert_awaited_once()

    @patch("likecodex_engine.setup_wizard.console")
    @patch("likecodex_engine.setup_wizard._step_provider_selection", return_value=None)
    @pytest.mark.asyncio
    async def test_wizard_cancelled_at_provider(
        self, mock_step: AsyncMock, mock_console: MagicMock
    ) -> None:
        # If provider selection returns None, wizard should exit early
        result = await run_setup_wizard()
        assert result is None  # run_setup_wizard returns None
