"""Context / conversation management optimized for DeepSeek prefix caching."""

from __future__ import annotations

import importlib.resources as pkg_resources
import json
from typing import Any

from likecodex_engine.context.compaction import ContextCompactor
from likecodex_engine.llm.base import Message, Role

DEFAULT_SYSTEM_PROMPT_PATH = "prompts/system.md"
CONTEXT_PREFIX = "[Context]\n"


def stable_json_dumps(value: Any) -> str:
    """Deterministic JSON serialization for cache-stable tool payloads."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_tool_calls_json(calls: list[dict[str, Any]]) -> str:
    """Serialize assistant tool_calls with stable key ordering."""
    return stable_json_dumps(calls)


def _default_system_prompt() -> str:
    """Load the default system prompt bundled with the package."""
    try:
        return pkg_resources.files("likecodex_engine").joinpath(DEFAULT_SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")
    except Exception:
        return "You are LikeCodex, a DeepSeek-powered software engineering agent."


class ContextManager:
    """Maintains message history with a stable SYSTEM prefix for cache hits."""

    def __init__(
        self,
        system_prompt: str | None = None,
        max_messages: int = 200,
        max_tokens: int = 60000,
        messages: list[Message] | None = None,
    ) -> None:
        self.max_messages = max_messages
        self.compactor = ContextCompactor(
            max_messages=max_messages,
            max_tokens=max_tokens,
        )
        if messages is not None:
            self.messages = list(messages)
        else:
            self.messages: list[Message] = []
            prompt = system_prompt if system_prompt is not None else _default_system_prompt()
            self.messages.append(Message(role=Role.SYSTEM, content=prompt))

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role=Role.USER, content=content))
        self._maybe_compact()

    def add_context_block(self, content: str) -> None:
        """Append dynamic context as a USER message (preserves static SYSTEM prefix)."""
        block = content if content.startswith(CONTEXT_PREFIX) else f"{CONTEXT_PREFIX}{content}"
        self.messages.append(Message(role=Role.USER, content=block))
        self._maybe_compact()

    def add_system_note(self, content: str) -> None:
        """Deprecated: routes to add_context_block for cache stability."""
        self.add_context_block(content)

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        raw_tool_calls: str | None = None,
    ) -> None:
        serialized = raw_tool_calls
        if tool_calls is not None and serialized is None:
            serialized = stable_tool_calls_json(tool_calls)
        self.messages.append(
            Message(
                role=Role.ASSISTANT,
                content=content,
                tool_calls=tool_calls,
                raw_tool_calls=serialized,
            )
        )
        self._maybe_compact()

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.messages.append(Message(role=Role.TOOL, content=content, tool_call_id=tool_call_id))
        self._maybe_compact()

    def get_messages(self) -> list[Message]:
        return self.build_for_llm()

    def build_for_llm(self) -> list[Message]:
        """Return messages with deterministic assistant tool_calls serialization."""
        out: list[Message] = []
        for message in self.messages:
            if message.role == Role.ASSISTANT and message.tool_calls:
                if message.raw_tool_calls:
                    tool_calls = json.loads(message.raw_tool_calls)
                else:
                    tool_calls = message.tool_calls
                out.append(
                    Message(
                        role=message.role,
                        content=message.content,
                        tool_calls=tool_calls,
                        raw_tool_calls=message.raw_tool_calls,
                    )
                )
            else:
                out.append(message.model_copy(deep=True))
        return out

    def _maybe_compact(self) -> None:
        self.messages = self.compactor.compact(self.messages)

    def estimate_tokens(self) -> int:
        total = 0
        for m in self.messages:
            total += len(m.content) // 4
            if m.raw_tool_calls:
                total += len(m.raw_tool_calls) // 4
            elif m.tool_calls:
                total += len(stable_tool_calls_json(m.tool_calls)) // 4
        return total
