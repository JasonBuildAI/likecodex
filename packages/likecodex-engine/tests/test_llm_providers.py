"""Tests for LLM providers with mocked backends."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from likecodex_engine.llm.anthropic import AnthropicProvider
from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, Role, ToolCall
from likecodex_engine.llm.fallback import (
    FallbackChain,
    _is_auth_error,
    _is_rate_limit,
    _is_retryable,
    _is_timeout,
    build_fallback_chain,
)
from likecodex_engine.llm.gemini import GeminiProvider
from likecodex_engine.llm.local import LocalProvider


# ── Helpers ─────────────────────────────────────────────────────

def _make_msg(content: str = "hello", role: Role = Role.USER) -> list[Message]:
    return [Message(role=role, content=content)]


# ── Mock provider for FallbackChain tests ───────────────────────

class MockProvider(LLMProvider):
    """A mock LLM provider for testing fallback chains."""

    def __init__(self, name: str, fail: bool = False) -> None:
        super().__init__(model="mock-model")
        self._name = name
        self._fail = fail

    async def complete(
        self,
        messages: list[Message],
        tools=None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if self._fail:
            raise RuntimeError("rate limit exceeded")
        return LLMResponse(content=f"response from {self._name}", model=self.model)

    async def stream(
        self,
        messages: list[Message],
        tools=None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        if self._fail:
            raise RuntimeError("rate limit exceeded")
        yield LLMResponse(content=f"stream from {self._name}", model=self.model, event_type="delta")
        yield LLMResponse(content="", model=self.model, event_type="assistant")


# ── Base provider tests ─────────────────────────────────────────

class TestLLMProviderBase:
    """Tests for the abstract LLMProvider base class."""

    def test_count_tokens_estimate(self) -> None:
        p = MockProvider("test")
        # 100 chars / 4 ≈ 25 tokens
        assert p.count_tokens("x" * 100) == 25

    def test_model_property(self) -> None:
        p = MockProvider("test")
        assert p.model == "mock-model"


# ── AnthropicProvider tests ─────────────────────────────────────

class TestAnthropicProvider:
    """Tests for AnthropicProvider with mocked client."""

    def test_to_anthropic_messages_system(self) -> None:
        msgs = [
            Message(role=Role.SYSTEM, content="You are helpful."),
            Message(role=Role.USER, content="Hi"),
        ]
        system, anthro = AnthropicProvider._to_anthropic_messages(msgs)
        assert system == "You are helpful."
        assert len(anthro) == 1
        assert anthro[0]["role"] == "user"

    def test_to_anthropic_messages_tool_result(self) -> None:
        msgs = [
            Message(role=Role.USER, content="check"),
            Message(role=Role.TOOL, content='{"ok": true}', tool_call_id="call_1"),
        ]
        system, anthro = AnthropicProvider._to_anthropic_messages(msgs)
        assert system is None
        assert len(anthro) == 2
        # Tool result should have content with type tool_result
        assert anthro[1]["content"][0]["type"] == "tool_result"

    def test_to_openai_tools_conversion(self) -> None:
        tools = [
            {
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {"type": "object", "properties": {}},
                }
            }
        ]
        result = AnthropicProvider._to_openai_tools(tools)
        assert result is not None
        assert result[0]["name"] == "read_file"
        assert result[0]["input_schema"] == {"type": "object", "properties": {}}

    def test_to_openai_tools_none(self) -> None:
        assert AnthropicProvider._to_openai_tools(None) is None

    def test_parse_usage_empty(self) -> None:
        assert AnthropicProvider._parse_usage(None) == {}

    @patch("likecodex_engine.llm.anthropic.AsyncAnthropic")
    @pytest.mark.asyncio
    async def test_complete(self, mock_anthropic: MagicMock) -> None:
        # Create a mock response
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(type="text", text="Hello from Claude")]
        mock_resp.model = "claude-3"
        mock_resp.stop_reason = "end_turn"
        mock_resp.usage = MagicMock(input_tokens=10, output_tokens=20)

        mock_client = mock_anthropic.return_value
        mock_client.messages.create = AsyncMock(return_value=mock_resp)

        provider = AnthropicProvider(model="claude-3", api_key="sk-test")
        response = await provider.complete(_make_msg())
        assert "Hello from Claude" in response.content
        assert response.model == "claude-3"

    @patch("likecodex_engine.llm.anthropic.AsyncAnthropic")
    @pytest.mark.asyncio
    async def test_complete_with_tool_use(self, mock_anthropic: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_content = MagicMock(type="tool_use", id="tu_1", name="read_file", input={"path": "/test"})
        mock_resp.content = [mock_content]
        mock_resp.model = "claude-3"
        mock_resp.stop_reason = "tool_use"
        mock_resp.usage = MagicMock(input_tokens=10, output_tokens=5)

        mock_client = mock_anthropic.return_value
        mock_client.messages.create = AsyncMock(return_value=mock_resp)

        provider = AnthropicProvider(model="claude-3", api_key="sk-test")
        response = await provider.complete(_make_msg(), tools=[{"function": {"name": "read_file"}}])
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "read_file"


# ── GeminiProvider tests ────────────────────────────────────────

class TestGeminiProvider:
    """Tests for GeminiProvider with mocked client."""

    def test_to_gemini_contents(self) -> None:
        msgs = [
            Message(role=Role.SYSTEM, content="System instruction."),
            Message(role=Role.USER, content="Hello"),
        ]
        contents = GeminiProvider._to_gemini_contents(msgs)
        # System messages are skipped in contents
        assert len(contents) == 1
        assert contents[0]["role"] == "user"
        assert contents[0]["parts"][0]["text"] == "Hello"

    def test_get_system_instruction(self) -> None:
        msgs = [
            Message(role=Role.SYSTEM, content="Be helpful."),
            Message(role=Role.USER, content="Hi"),
        ]
        instruction = GeminiProvider._get_system_instruction(msgs)
        assert instruction == "Be helpful."

    def test_get_system_instruction_none(self) -> None:
        msgs = [Message(role=Role.USER, content="Hi")]
        assert GeminiProvider._get_system_instruction(msgs) is None

    def test_to_gemini_tools_conversion(self) -> None:
        tools = [
            {
                "function": {
                    "name": "search",
                    "description": "Search tool",
                    "parameters": {"type": "object"},
                }
            }
        ]
        result = GeminiProvider._to_gemini_tools(tools)
        assert result is not None
        assert result[0]["function_declarations"][0]["name"] == "search"


# ── LocalProvider tests ─────────────────────────────────────────

class TestLocalProvider:
    """Tests for LocalProvider."""

    @patch("likecodex_engine.llm.local.OpenAIProvider")
    def test_init_local_endpoint(self, mock_openai: MagicMock) -> None:
        provider = LocalProvider(model="llama3", base_url="http://localhost:11434")
        assert provider.is_ollama is True
        assert "11434" in provider.endpoint

    @patch("likecodex_engine.llm.local.OpenAIProvider")
    def test_init_with_explicit_v1(self, mock_openai: MagicMock) -> None:
        provider = LocalProvider(model="llama3", base_url="http://localhost:8080/v1")
        assert provider.endpoint.endswith("/v1")

    @patch("likecodex_engine.llm.local._check_ollama_running", return_value=True)
    @patch("likecodex_engine.llm.local.OpenAIProvider")
    @pytest.mark.asyncio
    async def test_check_health_ok(
        self, mock_openai: MagicMock, mock_check: AsyncMock
    ) -> None:
        provider = LocalProvider(model="llama3")
        assert await provider.check_health() is True


# ── FallbackChain tests ─────────────────────────────────────────

class TestFallbackChain:
    """Tests for FallbackChain provider."""

    def test_requires_at_least_one_provider(self) -> None:
        with pytest.raises(ValueError, match="at least one provider"):
            FallbackChain([])

    def test_active_provider(self) -> None:
        chain = FallbackChain([MockProvider("primary")])
        assert chain.active_provider is not None

    def test_providers_property(self) -> None:
        p1 = MockProvider("a")
        p2 = MockProvider("b")
        chain = FallbackChain([p1, p2])
        assert len(chain.providers) == 2

    @pytest.mark.asyncio
    async def test_complete_first_provider_succeeds(self) -> None:
        chain = FallbackChain([MockProvider("primary")])
        response = await chain.complete(_make_msg())
        assert "response from primary" in response.content

    @pytest.mark.asyncio
    async def test_complete_fallback_on_failure(self) -> None:
        chain = FallbackChain([
            MockProvider("failing", fail=True),
            MockProvider("backup"),
        ])
        response = await chain.complete(_make_msg())
        assert "response from backup" in response.content

    @pytest.mark.asyncio
    async def test_complete_all_fail(self) -> None:
        chain = FallbackChain([
            MockProvider("a", fail=True),
            MockProvider("b", fail=True),
        ])
        with pytest.raises(RuntimeError):
            await chain.complete(_make_msg())

    @pytest.mark.asyncio
    async def test_stream_first_provider_succeeds(self) -> None:
        chain = FallbackChain([MockProvider("primary")])
        results = [r async for r in chain.stream(_make_msg())]
        assert len(results) == 2
        assert "stream from primary" in results[0].content

    @pytest.mark.asyncio
    async def test_stream_fallback_on_failure(self) -> None:
        chain = FallbackChain([
            MockProvider("a", fail=True),
            MockProvider("b"),
        ])
        results = [r async for r in chain.stream(_make_msg())]
        assert any("stream from b" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_non_retryable_error_raised(self) -> None:
        class NonRetryableProvider(MockProvider):
            async def complete(self, messages, tools=None, temperature=0.0, max_tokens=4096):
                raise ValueError("non-retryable error")

        chain = FallbackChain([NonRetryableProvider("test")])
        with pytest.raises(ValueError, match="non-retryable"):
            await chain.complete(_make_msg())

    def test_build_fallback_chain_default(self) -> None:
        chain = build_fallback_chain()
        assert len(chain.providers) == 4
        assert chain.model == "deepseek-v4-pro"

    def test_build_fallback_chain_custom(self) -> None:
        chain = build_fallback_chain([
            {"provider": "mock", "model": "mock-model"},
        ])
        assert len(chain.providers) == 1
        assert chain.model == "mock-model"


# ── Error classifier tests ──────────────────────────────────────

class TestErrorClassifiers:
    """Tests for the error classifier functions."""

    def test_is_auth_error_401(self) -> None:
        assert _is_auth_error(RuntimeError("HTTP 401 Unauthorized")) is True

    def test_is_auth_error_403(self) -> None:
        assert _is_auth_error(RuntimeError("403 Forbidden")) is True

    def test_is_auth_error_other(self) -> None:
        assert _is_auth_error(RuntimeError("500 Internal Error")) is False

    def test_is_rate_limit_429(self) -> None:
        assert _is_rate_limit(RuntimeError("HTTP 429 Too Many Requests")) is True

    def test_is_rate_limit_quota(self) -> None:
        assert _is_rate_limit(RuntimeError("quota exceeded")) is True

    def test_is_rate_limit_other(self) -> None:
        assert _is_rate_limit(RuntimeError("network error")) is False

    def test_is_timeout(self) -> None:
        assert _is_timeout(RuntimeError("timed out")) is True
        assert _is_timeout(RuntimeError("connection timeout")) is True
        assert _is_timeout(RuntimeError("normal error")) is False

    def test_is_retryable_combinations(self) -> None:
        assert _is_retryable(RuntimeError("HTTP 429 rate limit")) is True
        assert _is_retryable(RuntimeError("HTTP 401 unauthorized")) is True
        assert _is_retryable(RuntimeError("timed out")) is True
        assert _is_retryable(RuntimeError("normal error")) is False
