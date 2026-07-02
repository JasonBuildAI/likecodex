"""Factory for creating LLM providers from configuration."""

from __future__ import annotations

from likecodex_engine.llm.base import LLMProvider
from likecodex_engine.llm.claude import ClaudeProvider
from likecodex_engine.llm.deepseek import DeepSeekProvider
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.llm.ollama import OllamaProvider
from likecodex_engine.llm.openai import OpenAIProvider


def create_provider(
    provider: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    *,
    thinking: bool = False,
    thinking_budget: int | None = None,
    reasoning_effort: str = "",
    max_tokens: int | None = None,
) -> LLMProvider:
    """Create an LLM provider by name.

    Supported providers:
      - ``deepseek`` / ``deepseek-v4`` / ``deepseek-v4-flash`` / ``deepseek-v4-pro``
      - ``claude`` / ``anthropic``
      - ``ollama``
      - ``openai`` / ``azure``
      - ``mock``

    Environment variables for API keys:
      - ``DEEPSEEK_API_KEY``, ``LIKECODEX_LLM_API_KEY``
      - ``ANTHROPIC_API_KEY``
      - ``OLLAMA_BASE_URL`` (default ``http://localhost:11434``)
    """
    provider_norm = provider.lower()

    # ── DeepSeek ──────────────────────────────────────────────
    if provider_norm in {"deepseek", "deepseek-v4", "deepseek-v4-flash", "deepseek-v4-pro"}:
        return DeepSeekProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
        )

    # ── Claude ────────────────────────────────────────────────
    if provider_norm in {"claude", "anthropic"}:
        kwargs: dict = {
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "thinking": thinking,
        }
        if thinking_budget is not None:
            kwargs["thinking_budget"] = thinking_budget
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return ClaudeProvider(**kwargs)

    # ── Ollama ────────────────────────────────────────────────
    if provider_norm == "ollama":
        return OllamaProvider(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    # ── OpenAI / Azure ────────────────────────────────────────
    if provider_norm in {"openai", "azure"}:
        return OpenAIProvider(model=model, api_key=api_key, base_url=base_url)

    # ── Mock ──────────────────────────────────────────────────
    if provider_norm == "mock":
        return MockProvider.for_hello_world()

    raise ValueError(f"Unsupported LLM provider: {provider}")


def provider_from_config(
    cfg: dict,
    *,
    model_key: str = "model",
    thinking: bool | None = None,
) -> LLMProvider:
    """Create an LLM provider directly from a config dict.

    Example config dict::

        {
            "provider": "claude",
            "model": "claude-3-5-sonnet-latest",
            "api_key": "sk-ant-...",
            "thinking": True,
            "thinking_budget": 4096,
        }

    Parameters
    ----------
    cfg : dict
        Configuration dictionary. Supports all keys accepted by ``create_provider``.
    model_key : str
        Key under which the model name resides (default ``"model"``).
    thinking : bool | None
        Override the ``thinking`` flag. If ``None``, uses ``cfg.get("thinking", False)``.
    """
    return create_provider(
        cfg.get("provider", "deepseek"),
        cfg.get(model_key, "deepseek-v4-flash"),
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=bool(cfg.get("thinking", False)) if thinking is None else thinking,
        thinking_budget=cfg.get("thinking_budget"),
        reasoning_effort=str(cfg.get("reasoning_effort", "")),
        max_tokens=cfg.get("max_tokens"),
    )
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


def provider_from_config(
    cfg: dict,
    *,
    model_key: str = "model",
    thinking: bool | None = None,
) -> LLMProvider:
    """Create an LLM provider directly from a config dict."""
    return create_provider(
        cfg.get("provider", "deepseek"),
        cfg.get(model_key, "deepseek-v4-flash"),
        cfg.get("api_key"),
        cfg.get("base_url"),
        thinking=bool(cfg.get("thinking", False)) if thinking is None else thinking,
        reasoning_effort=str(cfg.get("reasoning_effort", "")),
    )
