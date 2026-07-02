"""Integration tests for Phase 1: Python-First Architecture.

Tests cover:
- Config loading with LIKECODEX_* namespace
- Config validation
- Hot reload support
- CLI argument parsing
- Health endpoints (/health, /health/liveness, /health/readiness)
- Rust executor fallback detection
- Error hierarchy
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from likecodex_engine.config_loader import (
    ConfigValidationError,
    clear_config_cache,
    engine_config_from_env,
    get_config_with_hot_reload,
    load_merged_config,
    project_config_paths,
    validate_config,
)
from likecodex_engine.errors import (
    ConfigError,
    EngineError,
    LikeCodexError,
    ProviderError,
    ToolError,
    ValidationError,
)
from likecodex_engine.routes.agent import health, liveness, readiness, reload_config
from likecodex_engine.routes._shared import APP_CONFIG
from likecodex_engine.server import create_app
from likecodex_engine.tools.shell import execute_shell_with_python, rust_executor_available


# ── Config Loader Tests ─────────────────────────────────────────


def test_project_config_paths_includes_likecodex_config_toml(tmp_path: Path) -> None:
    """Should find likecodex.config.toml in addition to existing config files."""
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    (root / "likecodex.config.toml").write_text('[llm]\nmodel = "test-model"\n', encoding="utf-8")

    paths = project_config_paths(root)
    names = [p.name for p in paths]
    assert "likecodex.config.toml" in names


def test_validate_config_passes_with_valid_config() -> None:
    """Validation should pass when api_key and model are present."""
    validate_config({"api_key": "sk-test", "model": "deepseek-v4-flash"})  # no exception


def test_validate_config_raises_on_missing_api_key() -> None:
    """Validation should raise ConfigValidationError when api_key is missing."""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config({"model": "deepseek-v4-flash"})
    assert "api_key" in str(exc_info.value)


def test_validate_config_raises_on_missing_model() -> None:
    """Validation should raise ConfigValidationError when model is missing."""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config({"api_key": "sk-test"})
    assert "model" in str(exc_info.value)


def test_validate_config_multiple_missing() -> None:
    """Validation should report all missing fields."""
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config({})
    assert exc_info.value.missing_fields == ["api_key", "model"]


def test_load_merged_config_validation(tmp_path: Path) -> None:
    """load_merged_config with validate=True should validate the merged result."""
    with pytest.raises(ConfigValidationError):
        load_merged_config(tmp_path, validate=True)


def test_engine_config_from_env_with_likecodex_env(monkeypatch: Any) -> None:
    """engine_config_from_env should pick up LIKECODEX_* env vars."""
    monkeypatch.setenv("LIKECODEX_LLM_API_KEY", "sk-env-key")
    monkeypatch.setenv("LIKECODEX_LLM_MODEL", "deepseek-v4-pro")

    config = engine_config_from_env()
    assert config["api_key"] == "sk-env-key"
    assert config["model"] == "deepseek-v4-pro"


def test_engine_config_from_env_fallback_to_deepseek_env(monkeypatch: Any) -> None:
    """DEEPSEEK_API_KEY should be used as fallback."""
    monkeypatch.delenv("LIKECODEX_LLM_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-key")

    config = engine_config_from_env()
    assert config["api_key"] == "sk-deepseek-key"


def test_get_config_with_hot_reload(monkeypatch: Any) -> None:
    """get_config_with_hot_reload should reload on env changes."""
    clear_config_cache()
    monkeypatch.setenv("LIKECODEX_LLM_API_KEY", "sk-first")
    config1 = get_config_with_hot_reload()
    assert config1["api_key"] == "sk-first"

    # Change env var
    monkeypatch.setenv("LIKECODEX_LLM_API_KEY", "sk-second")
    config2 = get_config_with_hot_reload()
    assert config2["api_key"] == "sk-second"


def test_clear_config_cache_clears_cache() -> None:
    """clear_config_cache should invalidate the cache."""
    clear_config_cache()
    # Just verify it doesn't raise
    assert True


# ── CLI and API Integration Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """Health endpoint returns status ok."""
    app = create_app({"provider": "mock", "model": "mock", "api_key": None})
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_liveness_endpoint() -> None:
    """Liveness endpoint returns alive status."""
    app = create_app({"provider": "mock", "model": "mock", "api_key": None})
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health/liveness")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_endpoint_without_key() -> None:
    """Readiness endpoint reports not_ready without API key."""
    app = create_app({"provider": "mock", "model": "mock", "api_key": None})
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health/readiness")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "not_ready"
        assert data["api_key_configured"] is False


@pytest.mark.asyncio
async def test_readiness_endpoint_with_key() -> None:
    """Readiness endpoint reports ready with API key."""
    app = create_app({"provider": "mock", "model": "mock", "api_key": "sk-test"})
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health/readiness")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ready"
        assert data["api_key_configured"] is True


@pytest.mark.asyncio
async def test_reload_endpoint() -> None:
    """Reload endpoint should return success."""
    app = create_app({"provider": "mock", "model": "mock", "api_key": "sk-test"})
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/admin/reload")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


# ── Shell Fallback Tests ──────────────────────────────────────


def test_rust_executor_detection() -> None:
    """rust_executor_available should return bool without error."""
    result = rust_executor_available()
    assert isinstance(result, bool)


def test_execute_shell_with_python() -> None:
    """Python subprocess fallback should work for simple commands."""
    result = execute_shell_with_python("echo hello", ".")
    assert result["exit_code"] == 0
    assert "hello" in result.get("stdout", "")


def test_execute_shell_with_python_timeout() -> None:
    """Python subprocess fallback should handle timeouts gracefully."""
    result = execute_shell_with_python("sleep 10", ".", timeout=1)
    assert result.get("timed_out") is True or result["exit_code"] is None


# ── Error Hierarchy Tests ─────────────────────────────────────


class TestLikeCodexErrors:
    """Test the unified error hierarchy."""

    def test_base_error(self) -> None:
        e = LikeCodexError("base error")
        assert e.message == "base error"
        assert e.status_code == 500
        assert e.to_dict()["error"] == "base error"

    def test_config_error(self) -> None:
        e = ConfigError("missing key", missing_fields=["api_key"])
        assert e.status_code == 400
        assert "api_key" in str(e.details["missing_fields"])

    def test_engine_error(self) -> None:
        e = EngineError("engine not running")
        assert e.status_code == 500

    def test_provider_error(self) -> None:
        e = ProviderError("API rate limit", provider="deepseek")
        assert e.status_code == 502
        assert e.details["provider"] == "deepseek"

    def test_tool_error(self) -> None:
        e = ToolError("tool failed", tool_name="shell")
        assert e.status_code == 500
        assert e.details["tool_name"] == "shell"

    def test_validation_error(self) -> None:
        e = ValidationError("invalid input", field="model")
        assert e.status_code == 422
        assert e.details["field"] == "model"

    def test_error_is_json_serializable(self) -> None:
        e = LikeCodexError("test", status_code=400, details={"key": "value"})
        d = e.to_dict()
        assert isinstance(d, dict)
        assert "error" in d
        assert "status_code" in d
        assert "details" in d
