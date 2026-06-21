"""Factory for creating LLM providers from configuration."""

from __future__ import annotations

from likecodex_engine.llm.base import LLMProvider
from likecodex_engine.llm.deepseek import DeepSeekProvider
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.llm.openai import OpenAIProvider


def create_provider(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    *,
    thinking: bool = False,
    reasoning_effort: str = "",
) -> LLMProvider:
    """Create an LLM provider by name."""
    provider_norm = provider.lower()
    if provider_norm in {"deepseek", "deepseek-v4", "deepseek-v4-flash", "deepseek-v4-pro"}:
        return DeepSeekProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
        )
    if provider_norm in {"openai", "azure"}:
        return OpenAIProvider(model=model, api_key=api_key, base_url=base_url)
    if provider_norm == "mock":
        return MockProvider.for_hello_world()
    raise ValueError(f"Unsupported LLM provider: {provider}")
