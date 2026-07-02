"""Runtime component availability detection for LikeCodex.

Provides a singleton ComponentAvailability service that checks whether
Rust-native components (CLI, sandbox, indexer, server) and Web UI static
files are present on the current system.

Results are cached for 30 seconds to avoid repeated filesystem checks.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "ComponentAvailability",
    "get_component_availability",
    "AvailabilityCache",
]

# -- Cache expiry in seconds ------------------------------------------------
CACHE_TTL: float = 30.0


@dataclass
class AvailabilityCache:
    """Holds cached availability results plus a timestamp."""

    cached_at: float = 0.0
    rust_cli: bool = False
    sandbox: bool = False
    indexer: bool = False
    server: bool = False
    web_ui: bool = False

    def is_expired(self, now: float | None = None) -> bool:
        """Return True if the cache is older than CACHE_TTL."""
        return (now or time.time()) - self.cached_at > CACHE_TTL


class ComponentAvailability:
    """Singleton that detects installed LikeCodex components.

    Each *available property checks for the corresponding component's
    binary or build artefacts and caches the result.
    """

    _instance: ComponentAvailability | None = None

    def __new__(cls) -> ComponentAvailability:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = AvailabilityCache()
        return cls._instance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _cache: AvailabilityCache

    @property
    def _project_root(self) -> Path:
        """Resolve the project root (parent of the Cargo workspace root)."""
        # Look for Cargo.toml or pyproject.toml markers
        cwd = Path.cwd().resolve()
        for parent in (cwd, *cwd.parents):
            if (parent / "Cargo.toml").exists():
                return parent
        return cwd

    @property
    def _target_release(self) -> Path:
        return self._project_root / "target" / "release"

    @property
    def _web_dir(self) -> Path:
        return self._project_root / "web"

    def _binary_path(self, name: str) -> Path:
        """Return the expected path for a Rust binary."""
        if os.name == "nt":
            return self._target_release / f"{name}.exe"
        return self._target_release / name

    # ------------------------------------------------------------------
    # Public properties (lazily cached)
    # ------------------------------------------------------------------

    @property
    def rust_cli(self) -> bool:
        """Whether the Rust CLI binary (likecodex) is available."""
        if self._cache.is_expired():
            self._refresh()
        return self._cache.rust_cli

    @property
    def sandbox(self) -> bool:
        """Whether the sandbox binary is available."""
        if self._cache.is_expired():
            self._refresh()
        return self._cache.sandbox

    @property
    def indexer(self) -> bool:
        """Whether the indexer binary is available."""
        if self._cache.is_expired():
            self._refresh()
        return self._cache.indexer

    @property
    def server(self) -> bool:
        """Whether the server binary is available."""
        if self._cache.is_expired():
            self._refresh()
        return self._cache.server

    @property
    def web_ui(self) -> bool:
        """Whether the Web UI static files exist (built Next.js output)."""
        if self._cache.is_expired():
            self._refresh()
        return self._cache.web_ui

    @property
    def any_rust_available(self) -> bool:
        """Return True if at least one Rust component is available."""
        return any([self.rust_cli, self.sandbox, self.indexer, self.server])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Force an immediate cache refresh."""
        self._cache = self._detect()

    def summary(self) -> dict[str, bool]:
        """Return a flat dictionary of all component states."""
        if self._cache.is_expired():
            self._refresh()
        return {
            "rust_cli": self._cache.rust_cli,
            "sandbox": self._cache.sandbox,
            "indexer": self._cache.indexer,
            "server": self._cache.server,
            "web_ui": self._cache.web_ui,
        }

    def invalidate(self) -> None:
        """Force the cache to expire on the next access."""
        self._cache.cached_at = 0.0

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._cache = self._detect()

    def _detect(self) -> AvailabilityCache:
        release = self._target_release
        has_release_dir = release.is_dir()

        return AvailabilityCache(
            cached_at=time.time(),
            rust_cli=has_release_dir and self._binary_path("likecodex").is_file(),
            sandbox=has_release_dir and self._binary_path("likecodex-sandbox").is_file(),
            indexer=has_release_dir and self._binary_path("likecodex-indexer").is_file(),
            server=has_release_dir and self._binary_path("likecodex-server").is_file(),
            web_ui=(self._web_dir / ".next" / "index.html").is_file()
            or (self._web_dir / ".next" / "index.htm").is_file(),
        )


# -- Module-level helper ----------------------------------------------------

_global_availability: ComponentAvailability | None = None


def get_component_availability() -> ComponentAvailability:
    """Return the global ComponentAvailability singleton."""
    global _global_availability
    if _global_availability is None:
        _global_availability = ComponentAvailability()
    return _global_availability
