"""Tests for the ComponentAvailability module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from likecodex_engine.component_availability import (
    AvailabilityCache,
    ComponentAvailability,
    get_component_availability,
)


class TestAvailabilityCache:
    """Tests for the AvailabilityCache data model."""

    def test_default_values(self) -> None:
        cache = AvailabilityCache()
        assert cache.rust_cli is False
        assert cache.sandbox is False
        assert cache.indexer is False
        assert cache.server is False
        assert cache.web_ui is False
        assert cache.cached_at == 0.0

    def test_expired_by_default(self) -> None:
        cache = AvailabilityCache()
        assert cache.is_expired() is True

    def test_not_expired_recent(self) -> None:
        import time

        cache = AvailabilityCache(cached_at=time.time())
        assert cache.is_expired() is False

    def test_expired_after_ttl(self) -> None:
        cache = AvailabilityCache(cached_at=0.0)
        assert cache.is_expired() is True


class TestComponentAvailability:
    """Tests for the ComponentAvailability singleton."""

    def test_singleton_pattern(self) -> None:
        a = ComponentAvailability()
        b = ComponentAvailability()
        assert a is b

    def test_invalidate_force_expiry(self) -> None:
        ca = ComponentAvailability()
        ca._cache = AvailabilityCache(cached_at=9999999999.0)
        ca.invalidate()
        assert ca._cache.cached_at == 0.0

    @patch.object(ComponentAvailability, "_target_release", new_callable=PropertyMock)
    @patch.object(ComponentAvailability, "_web_dir", new_callable=PropertyMock)
    @patch("pathlib.Path.is_dir", return_value=True)
    @patch("pathlib.Path.is_file", side_effect=lambda: True)
    def test_all_components_available(
        self,
        mock_is_file: MagicMock,
        mock_is_dir: MagicMock,
        mock_web_dir: PropertyMock,
        mock_target: PropertyMock,
    ) -> None:
        # Disable the __new__ singleton cache for this test
        ComponentAvailability._instance = None
        mock_target.return_value = Path("/fake/target/release")
        mock_web_dir.return_value = Path("/fake/web")

        ca = ComponentAvailability()
        ca.invalidate()

        assert ca.rust_cli is True
        assert ca.sandbox is True
        assert ca.indexer is True
        assert ca.server is True
        assert ca.web_ui is True
        assert ca.any_rust_available is True

    @patch.object(ComponentAvailability, "_target_release", new_callable=PropertyMock)
    @patch.object(ComponentAvailability, "_web_dir", new_callable=PropertyMock)
    @patch("pathlib.Path.is_dir", return_value=False)
    @patch("pathlib.Path.is_file", return_value=False)
    def test_no_components_available(
        self,
        mock_is_file: MagicMock,
        mock_is_dir: MagicMock,
        mock_web_dir: PropertyMock,
        mock_target: PropertyMock,
    ) -> None:
        ComponentAvailability._instance = None
        mock_target.return_value = Path("/fake/target/release")
        mock_web_dir.return_value = Path("/fake/web")

        ca = ComponentAvailability()
        ca.invalidate()

        assert ca.rust_cli is False
        assert ca.sandbox is False
        assert ca.indexer is False
        assert ca.server is False
        assert ca.web_ui is False
        assert ca.any_rust_available is False

    def test_summary_returns_dict(self) -> None:
        ComponentAvailability._instance = None
        ca = ComponentAvailability()
        summary = ca.summary()
        assert isinstance(summary, dict)
        for key in ("rust_cli", "sandbox", "indexer", "server", "web_ui"):
            assert key in summary

    def test_refresh_forces_detection(self) -> None:
        ComponentAvailability._instance = None
        ca = ComponentAvailability()
        ca._cache = AvailabilityCache(cached_at=9999999999.0, rust_cli=False)
        assert ca.rust_cli is False  # Uses cached

        # After refresh with mock detection returning True
        with patch.object(ca, "_detect", return_value=AvailabilityCache(
            cached_at=9999999999.0, rust_cli=True
        )):
            ca.refresh()
            assert ca.rust_cli is True


class TestGetComponentAvailability:
    """Tests for the module-level helper."""

    def test_returns_singleton(self) -> None:
        ComponentAvailability._instance = None
        a = get_component_availability()
        b = get_component_availability()
        assert a is b
        assert isinstance(a, ComponentAvailability)
