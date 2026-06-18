"""Context / conversation management."""

from __future__ import annotations

import importlib.resources as pkg_resources
from typing import Any

from likecodex_engine.context.compaction import ContextCompactor
from likecodex_engine.llm.base import Message, Role

DEFAULT_SYSTEM_PROMPT_PATH = "prompts/system.md"


def _default_system_prompt() -> str:
    """Load the default system prompt bundled with the package."""
    try:
        return pkg_resources.files("likecodex_engine").joinpath(DEFAULT_SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")
    except Exception:
        # Fallback if the package resource is not available.
        return "You are LikeCodex, a helpful software engineering agent."


class ContextManager:
    """Maintains the message history for an agent session."""

    def __init__(
        self,
        system_prompt: str | None = None,
        max_messages: int = 200,
        max_tokens: int = 60000,
    ) -> None:
        self.max_messages = max_messages
        self.compactor = ContextCompactor(
            max_messages=max_messages,
            max_tokens=max_tokens,
        )
        self.messages: list[Message] = []
        prompt = system_prompt if system_prompt is not None else _default_system_prompt()
        self.messages.append(Message(role=Role.SYSTEM, content=prompt))

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role=Role.USER, content=content))
        self._maybe_compact()

    def add_system_note(self, content: str) -> None:
        self.messages.append(Message(role=Role.SYSTEM, content=content))
        self._maybe_compact()

    def add_assistant_message(self, content: str, tool_calls: list[dict[str, Any]] | None = None) -> None:
        self.messages.append(Message(role=Role.ASSISTANT, content=content, tool_calls=tool_calls))
        self._maybe_compact()

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.messages.append(Message(role=Role.TOOL, content=content, tool_call_id=tool_call_id))
        self._maybe_compact()

    def get_messages(self) -> list[Message]:
        return list(self.messages)

    def _maybe_compact(self) -> None:
        self.messages = self.compactor.compact(self.messages)

    def estimate_tokens(self) -> int:
        total = 0
        for m in self.messages:
            total += len(m.content) // 4
            if m.tool_calls:
                total += len(str(m.tool_calls)) // 4
        return total
