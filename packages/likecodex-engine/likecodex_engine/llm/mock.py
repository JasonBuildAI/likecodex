"""Mock LLM provider for tests and offline development."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from likecodex_engine.llm.base import LLMProvider, LLMResponse, Message, ToolCall


class MockProvider(LLMProvider):
    """A deterministic LLM provider that returns scripted responses."""

    def __init__(self, responses: list[LLMResponse] | None = None, simulate_cache: bool = False) -> None:
        super().__init__("mock")
        self.responses = responses or []
        self.calls: list[list[Message]] = []
        self.index = 0
        self.simulate_cache = simulate_cache

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.calls.append(messages)
        if self.index < len(self.responses):
            resp = self.responses[self.index]
            self.index += 1
            if self.simulate_cache and len(self.calls) > 1:
                usage = dict(resp.usage or {})
                usage.setdefault("prompt_cache_hit_tokens", 800)
                usage.setdefault("prompt_cache_miss_tokens", 50)
                usage.setdefault("prompt_tokens", 850)
                usage.setdefault("completion_tokens", 20)
                resp = resp.model_copy(update={"usage": usage})
            return resp
        usage = None
        if self.simulate_cache and len(self.calls) > 1:
            usage = {
                "prompt_cache_hit_tokens": 800,
                "prompt_cache_miss_tokens": 50,
                "prompt_tokens": 850,
                "completion_tokens": 10,
            }
        return LLMResponse(content="No more scripted responses.", usage=usage)

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        yield await self.complete(messages, tools, temperature, max_tokens)

    @staticmethod
    def responses_default() -> LLMResponse:
        """Return a simple text-only response."""
        return LLMResponse(content="hi")

    @classmethod
    def for_hello_world(cls) -> MockProvider:
        """Return a mock that writes and runs hello.py."""
        return cls(
            responses=[
                LLMResponse(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            name="write_file",
                            arguments={"path": "hello.py", "content": "print('hello world')"},
                        )
                    ],
                ),
                LLMResponse(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="call_2",
                            name="run_command",
                            arguments={"command": "python hello.py"},
                        )
                    ],
                ),
                LLMResponse(content="Created hello.py and ran it successfully."),
            ]
        )

    @classmethod
    def for_cache_test(cls, turns: int = 10) -> MockProvider:
        """Return a mock that simulates cache hits from turn 2 onward."""
        return cls(
            simulate_cache=True,
            responses=[LLMResponse(content=f"Response turn {i}.") for i in range(1, turns + 1)],
        )
