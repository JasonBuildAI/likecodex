"""Ollama LLM provider — direct HTTP API (no SDK dependency), model detection, tool calling."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, ToolCall

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
CONNECTION_TIMEOUT = 30  # seconds


# ── Helper: resolve base URL ──────────────────────────────────

def _resolve_base_url(base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def _resolve_api_key(api_key: str | None) -> str:
    """Ollama doesn't need an API key, but we accept one for consistency."""
    if api_key:
        return api_key
    return os.environ.get("OLLAMA_API_KEY", "")


# ── Helper: convert messages to Ollama format ─────────────────

def _to_ollama_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert internal messages to Ollama chat format (OpenAI-compatible)."""
    out: list[dict[str, Any]] = []
    for m in messages:
        item: dict[str, Any] = {"role": m.role.value, "content": m.content}
        if m.tool_calls:
            item["tool_calls"] = m.tool_calls
        if m.tool_call_id:
            item["tool_call_id"] = m.tool_call_id
        if m.name:
            item["name"] = m.name
        out.append(item)
    return out


# ── Helper: build Ollama-format tools ────────────────────────

def _to_ollama_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Ollama uses the same format as OpenAI for tool definitions."""
    if not tools:
        return None
    return tools  # Ollama /v1/chat/compatibles endpoint accepts OpenAI-format tools


# ── Helper: parse tool calls from response ───────────────────

def _parse_tool_calls(raw_choices: list[dict[str, Any]]) -> list[ToolCall]:
    """Extract ToolCall objects from an Ollama chat response."""
    tool_calls: list[ToolCall] = []
    for choice in raw_choices:
        msg = choice.get("message", {})
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", fn.get("name", "ollama_call")),
                    name=fn.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )
    return tool_calls


# ── Provider ──────────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    """Ollama provider using direct HTTP calls against the Ollama API.

    Supports:
      - Streaming (``stream()``) and non-streaming (``complete()``)
      - Tool / function calling (OpenAI-compatible format)
      - Automatic model detection via ``/api/tags``
      - Runtime model switching via ``switch_model()``

    Does **not** depend on the ``ollama`` Python SDK — uses ``aiohttp`` directly.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model, api_key, base_url)
        self._base_url = _resolve_base_url(base_url)
        self._api_key = _resolve_api_key(api_key)
        self._session: aiohttp.ClientSession | None = None
        self._available_models: list[str] = []

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=CONNECTION_TIMEOUT),
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Model detection
    # ------------------------------------------------------------------

    async def list_models(self) -> list[str]:
        """Fetch available models from Ollama ``/api/tags``.

        Returns model names (e.g. ``["llama3.2:latest", "qwen2.5:7b"]``).
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags") as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                models = data.get("models", [])
                self._available_models = [
                    m.get("name", "") for m in models if m.get("name")
                ]
                return self._available_models
        except Exception:
            return []

    async def has_model(self, model_name: str) -> bool:
        """Check whether a specific model is available locally."""
        available = await self.list_models()
        return any(model_name in m for m in available)

    @property
    def available_models(self) -> list[str]:
        """Cached model list (call ``list_models()`` to refresh)."""
        return list(self._available_models)

    def switch_model(self, model: str) -> None:
        """Switch the active model at runtime."""
        self.model = model

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def check_health(self) -> bool:
        """Check whether the Ollama server is reachable."""
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags", timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Complete (non-streaming)
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        ollama_messages = _to_ollama_messages(messages)
        ollama_tools = _to_ollama_tools(tools)
        session = await self._get_session()

        body: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if ollama_tools:
            body["tools"] = ollama_tools

        async with session.post(f"{self._base_url}/v1/chat/completions", json=body) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"Ollama API error ({resp.status}): {error_text[:500]}")
            data = await resp.json()

        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        tool_calls = _parse_tool_calls(choices)

        usage: dict[str, Any] = {}
        raw_usage = data.get("usage")
        if raw_usage:
            usage = {
                "prompt_tokens": int(raw_usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(raw_usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(raw_usage.get("total_tokens", 0) or 0),
            }

        finish_reason = choices[0].get("finish_reason", "") if choices else ""
        if finish_reason:
            usage["finish_reason"] = finish_reason

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", self.model),
            usage=usage or None,
        )

    # ------------------------------------------------------------------
    # Stream
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        ollama_messages = _to_ollama_messages(messages)
        ollama_tools = _to_ollama_tools(tools)
        session = await self._get_session()

        body: dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if ollama_tools:
            body["tools"] = ollama_tools

        content_parts: list[str] = []
        pending_tools: dict[int, dict[str, Any]] = {}
        usage: dict[str, Any] = {}
        finish_reason: str | None = None
        emitted = False
        model_name = self.model

        async with session.post(f"{self._base_url}/v1/chat/completions", json=body) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"Ollama API error ({resp.status}): {error_text[:500]}")

            try:
                async for line in resp.content:
                    if not line:
                        continue
                    line_text = line.decode("utf-8", errors="replace").strip()
                    if not line_text:
                        continue
                    if line_text == "data: [DONE]":
                        break
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]

                    try:
                        chunk = json.loads(line_text)
                    except json.JSONDecodeError:
                        continue

                    # Track usage
                    raw_usage = chunk.get("usage")
                    if raw_usage:
                        usage = {
                            "prompt_tokens": int(raw_usage.get("prompt_tokens", 0) or 0),
                            "completion_tokens": int(raw_usage.get("completion_tokens", 0) or 0),
                            "total_tokens": int(raw_usage.get("total_tokens", 0) or 0),
                        }

                    # Track model name from first chunk
                    chunk_model = chunk.get("model")
                    if chunk_model:
                        model_name = chunk_model

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    choice = choices[0]
                    delta = choice.get("delta", {})

                    # Finish reason
                    fr = choice.get("finish_reason")
                    if fr:
                        finish_reason = fr

                    # Text delta
                    text = delta.get("content", "")
                    if text:
                        emitted = True
                        content_parts.append(text)
                        yield LLMResponse(
                            content=text,
                            model=model_name,
                            event_type="delta",
                        )

                    # Tool call delta
                    tc_list = delta.get("tool_calls")
                    if tc_list:
                        for tc in tc_list:
                            idx = tc.get("index", 0) if "index" in tc else 0
                            slot = pending_tools.setdefault(
                                idx,
                                {"id": "", "name": "", "arguments": []},
                            )
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                slot["name"] = fn["name"]
                                emitted = True
                                yield LLMResponse(
                                    content="",
                                    model=model_name,
                                    event_type="tool_dispatch",
                                    metadata={"tool_name": fn["name"], "partial": True},
                                )
                            if fn.get("arguments"):
                                slot["arguments"].append(fn["arguments"])

            except Exception as exc:
                if emitted:
                    # Already sent partial output — don't retry
                    pass
                raise

        # Assemble final tool calls
        tool_calls: list[ToolCall] = []
        for idx in sorted(pending_tools):
            slot = pending_tools[idx]
            args_text = "".join(slot["arguments"])
            parsed = _safe_parse_json(args_text) if args_text else {}
            tool_calls.append(
                ToolCall(
                    id=slot["id"] or f"call_{idx}",
                    name=slot["name"],
                    arguments=parsed,
                )
            )

        final_content = "".join(content_parts)
        if final_content or tool_calls:
            merged_usage = dict(usage)
            if finish_reason:
                merged_usage["finish_reason"] = finish_reason
            yield LLMResponse(
                content=final_content,
                tool_calls=tool_calls,
                model=model_name,
                usage=merged_usage or None,
                event_type="assistant",
            )

    # ------------------------------------------------------------------
    # Token count (best-effort)
    # ------------------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """Best-effort token count for Ollama models."""
        return len(text) // 4


def _safe_parse_json(raw: str) -> dict[str, Any]:
    """Attempt to parse JSON; return empty dict on failure."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
