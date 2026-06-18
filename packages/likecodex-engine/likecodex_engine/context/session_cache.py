"""Session context cache for multi-turn DeepSeek prefix reuse."""

from __future__ import annotations

from likecodex_engine.context.manager import ContextManager


class SessionContextCache:
    """In-process cache mapping session_id to ContextManager instances."""

    def __init__(self) -> None:
        self._contexts: dict[str, ContextManager] = {}

    def get(self, session_id: str) -> ContextManager | None:
        return self._contexts.get(session_id)

    def put(self, session_id: str, context: ContextManager) -> None:
        self._contexts[session_id] = context

    def pop(self, session_id: str) -> None:
        self._contexts.pop(session_id, None)

    def clear(self) -> None:
        self._contexts.clear()
