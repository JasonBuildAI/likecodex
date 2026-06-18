"""Context compaction strategies for long conversations."""

from __future__ import annotations

from likecodex_engine.llm.base import Message, Role


class ContextCompactor:
    """Compresses conversation history to fit within token limits."""

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
        user_goal = next((m for m in messages if m.role == Role.USER), None)

        # Keep the most recent half, plus system and original user goal.
        keep_count = max(self.max_messages // 2, 1)
        recent = messages[-keep_count:]
        preserved: list[Message] = []
        if system:
            preserved.append(system)
        if user_goal and user_goal not in recent:
            preserved.append(user_goal)
            preserved.append(
                Message(
                    role=Role.SYSTEM,
                    content="[Intermediate conversation turns summarized or omitted due to context limits.]",
                )
            )
        preserved.extend(recent)
        return preserved

    def _estimate_tokens(self, messages: list[Message]) -> int:
        total = 0
        for m in messages:
            total += len(m.content) // 4
            if m.tool_calls:
                total += len(str(m.tool_calls)) // 4
        return total
