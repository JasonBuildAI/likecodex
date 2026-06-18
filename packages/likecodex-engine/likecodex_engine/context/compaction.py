"""Context compaction strategies for cache-first conversations."""

from __future__ import annotations

from likecodex_engine.llm.base import Message, Role


class ContextCompactor:
    """Legacy tail-only compactor (deprecated; use CacheFirstCompactor)."""

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
        body = messages[1:] if system else list(messages)
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
        return total


class CacheFirstCompactor:
    """Low-frequency compaction at cache-reset points only."""

    def __init__(
        self,
        max_messages: int = 200,
        context_window: int = 1_000_000,
        compact_ratio: float = 0.8,
    ) -> None:
        self.max_messages = max_messages
        self.context_window = context_window
        self.compact_ratio = compact_ratio

    def should_compact(self, prompt_tokens: int) -> bool:
        threshold = int(self.context_window * self.compact_ratio)
        return prompt_tokens >= threshold

    def summarize_log(self, log: list[Message]) -> str:
        """Rule-based summary for cache reset (no extra LLM call)."""
        user_msgs = [m.content[:120] for m in log if m.role == Role.USER][-3:]
        tool_count = sum(1 for m in log if m.role == Role.TOOL)
        assistant_count = sum(1 for m in log if m.role == Role.ASSISTANT)
        parts = [
            "Previous conversation summarized due to context limits.",
            f"Turns: {assistant_count} assistant, {tool_count} tool results.",
        ]
        if user_msgs:
            parts.append("Recent user goals: " + " | ".join(user_msgs))
        return "\n".join(parts)

    def emergency_trim(self, log: list[Message]) -> list[Message]:
        """Fallback when message count exceeds max (tail-only)."""
        if len(log) <= self.max_messages:
            return log
        return log[-self.max_messages :]
