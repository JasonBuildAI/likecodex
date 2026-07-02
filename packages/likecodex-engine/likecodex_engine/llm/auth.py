"""ProviderAuth – multi-provider API key management with rotation support."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderCredentials:
    """Credentials for a single provider."""

    api_keys: list[str] = field(default_factory=list)
    base_url: str = ""
    current_index: int = 0

    @property
    def active_key(self) -> str:
        if not self.api_keys:
            return ""
        return self.api_keys[self.current_index % len(self.api_keys)]

    def rotate(self) -> str:
        """Rotate to the next key and return it."""
        if len(self.api_keys) <= 1:
            return self.active_key
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        return self.active_key


class ProviderAuth:
    """Centralised API key manager for all supported LLM providers.

    Resolves keys from multiple environment variables and supports
    runtime key rotation.
    """

    # Mapping: provider name -> list of env vars to check (in priority order)
    _ENV_MAP: dict[str, list[str]] = {
        "openai": [
            "LIKECODEX_LLM_API_KEY",
            "OPENAI_API_KEY",
        ],
        "anthropic": [
            "ANTHROPIC_API_KEY",
        ],
        "gemini": [
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
        ],
        "deepseek": [
            "DEEPSEEK_API_KEY",
            "LIKECODEX_LLM_API_KEY",
        ],
        "azure": [
            "AZURE_OPENAI_API_KEY",
            "AZURE_API_KEY",
        ],
        "local": [
            "LOCAL_LLM_API_KEY",
        ],
    }

    _BASE_URL_MAP: dict[str, list[str]] = {
        "openai": [
            "OPENAI_BASE_URL",
        ],
        "anthropic": [
            "ANTHROPIC_BASE_URL",
        ],
        "deepseek": [
            "DEEPSEEK_BASE_URL",
        ],
        "azure": [
            "AZURE_OPENAI_ENDPOINT",
        ],
        "local": [
            "LOCAL_LLM_BASE_URL",
        ],
    }

    def __init__(self) -> None:
        self._credentials: dict[str, ProviderCredentials] = {}

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def auto_register_all(self) -> None:
        """Scan environment variables and register all found providers."""
        for provider in self._ENV_MAP:
            self._resolve(provider)

    def register(self, provider_name: str, api_key: str, base_url: str = "") -> None:
        """Manually register a credential entry."""
        entry = self._credentials.setdefault(
            provider_name,
            ProviderCredentials(),
        )
        if api_key not in entry.api_keys:
            entry.api_keys.append(api_key)
        if base_url:
            entry.base_url = base_url

    def _resolve(self, provider: str) -> None:
        """Resolve credentials from env vars for *provider*."""
        keys: list[str] = []
        for var in self._ENV_MAP.get(provider, []):
            val = os.environ.get(var, "")
            if val:
                keys.append(val)

        base_url = ""
        for var in self._BASE_URL_MAP.get(provider, []):
            val = os.environ.get(var, "")
            if val:
                base_url = val
                break

        if keys:
            self._credentials[provider] = ProviderCredentials(
                api_keys=keys,
                base_url=base_url,
            )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, provider: str) -> ProviderCredentials:
        """Get credentials for *provider*, resolving from env if not cached."""
        if provider not in self._credentials:
            self._resolve(provider)
        return self._credentials.get(provider, ProviderCredentials())

    def get_api_key(self, provider: str) -> str:
        """Get the active API key for *provider*."""
        return self.get(provider).active_key

    def get_base_url(self, provider: str) -> str:
        """Get the base URL for *provider*."""
        return self.get(provider).base_url

    def rotate_key(self, provider: str) -> str:
        """Rotate the API key for *provider* and return the new key."""
        return self.get(provider).rotate()

    def has_provider(self, provider: str) -> bool:
        """Check if *provider* has at least one API key configured."""
        creds = self.get(provider)
        return bool(creds.api_keys)

    def available_providers(self) -> list[str]:
        """Return list of provider names that have keys configured."""
        return [p for p in self._ENV_MAP if self.has_provider(p)]

    def __repr__(self) -> str:
        available = self.available_providers()
        return f"ProviderAuth(available={available})"
