"""Local LLM provider using OpenAI-compatible API (Ollama / llama.cpp / vLLM)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, ToolCall
from likecodex_engine.llm.openai import OpenAIProvider


DEFAULT_OLLAMA_URL = "http://localhost:11434"


async def _check_ollama_running(base_url: str) -> bool:
    """Check if an Ollama server is reachable at *base_url*."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/api/tags", timeout=5) as resp:
                return resp.status == 200
    except Exception:
        return False


class LocalProvider(LLMProvider):
    """Provider for local models served via an OpenAI-compatible endpoint.

    Supports:
      - Ollama (default http://localhost:11434)
      - llama.cpp server
      - vLLM
      - Any OpenAI-compatible local endpoint
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model, api_key, base_url)
        resolved_url = base_url or os.environ.get("LOCAL_LLM_BASE_URL", DEFAULT_OLLAMA_URL)
        resolved_key = api_key or os.environ.get("LOCAL_LLM_API_KEY", "")

        # Normalise: Ollama uses /v1/chat/completions compatible endpoint
        self.endpoint = resolved_url.rstrip("/")
        if not self.endpoint.endswith("/v1"):
            # Check if bare Ollama URL was given → append /v1
            self.endpoint = f"{self.endpoint}/v1"

        # Reuse the OpenAI provider under the hood with the local endpoint
        self._openai: OpenAIProvider = OpenAIProvider(
            model=model,
            api_key=resolved_key,
            base_url=self.endpoint,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def is_ollama(self) -> bool:
        return "11434" in self.endpoint or "ollama" in self.endpoint

    async def check_health(self) -> bool:
        """Check whether the local model server is reachable."""
        base = self.endpoint.replace("/v1", "").replace("/v1/", "")
        return await _check_ollama_running(base)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return await self._openai.complete(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        async for event in self._openai.stream(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield event
