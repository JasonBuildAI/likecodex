"""Base abstractions for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    role: Role
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    raw_tool_calls: str | None = None


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str = ""
    usage: dict[str, Any] | None = None
    event_type: str = "assistant"  # assistant | tool_result | permission | error | plan
    metadata: dict[str, Any] | None = None


class LLMProvider(ABC):
    """Abstract base for all LLM backends."""

    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a single completion."""

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[LLMResponse]:
        """Stream completion deltas."""

    def count_tokens(self, text: str) -> int:
        """Best-effort token count; subclasses may override."""
        return len(text) // 4
