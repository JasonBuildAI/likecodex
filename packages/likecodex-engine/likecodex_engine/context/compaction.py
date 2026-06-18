"""Context compaction strategies for long conversations."""

from __future__ import annotations

from likecodex_engine.llm.base import Message, Role


class ContextCompactor:
    """Compresses conversation history while preserving the static SYSTEM prefix."""

    def __init__(self, max_messages: int = 100, max_tokens: int = 60000) -> None:
        self.max_messages = max_messages
        self.max_tokens = max_tokens

    def compact(self, messages: list[Message]) -> list[Message]:
        if not messages:
            return messages

        current_tokens = self._estimate_tokens(messages)
        if len(messages) <= self.max_messages and current_tokens <= self.max_tokens:
            return messages

        system = messages[0] if messages[0].role == Role.SYSTEM else None
        body = messages[1:] if system else messages

        # Tail-only trim: drop oldest turns from the front of the body.
        while body and (
            len(body) + (1 if system else 0) > self.max_messages
            or self._estimate_tokens([m for m in ([system] if system else []) + body]) > self.max_tokens
        ):
            body.pop(0)

        preserved: list[Message] = []
        if system:
            preserved.append(system)
        preserved.extend(body)
        return preserved

    def _estimate_tokens(self, messages: list[Message]) -> int:
        total = 0
        for m in messages:
            total += len(m.content) // 4
            if m.raw_tool_calls:
                total += len(m.raw_tool_calls) // 4
            elif m.tool_calls:
                total += len(str(m.tool_calls)) // 4
        return total
