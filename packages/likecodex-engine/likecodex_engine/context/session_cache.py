"""Session context cache with LRU eviction for multi-turn DeepSeek prefix reuse."""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from likecodex_engine.context.manager import ContextManager


class SessionContextCache:
    """In-process cache mapping session_id to ContextManager instances.
    
    Uses LRU eviction to prevent memory leak from long-running sessions.
    Default max size: 100 sessions. Oldest accessed sessions are evicted first.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._max_size = max_size
        self._contexts: OrderedDict[str, ContextManager] = OrderedDict()

    def get(self, session_id: str) -> Optional[ContextManager]:
        ctx = self._contexts.get(session_id)
        if ctx is not None:
            self._contexts.move_to_end(session_id)
        return ctx

    def put(self, session_id: str, context: ContextManager) -> None:
        if session_id in self._contexts:
            self._contexts.move_to_end(session_id)
        else:
            self._contexts[session_id] = context
            self._evict_if_needed()

    def pop(self, session_id: str) -> None:
        self._contexts.pop(session_id, None)

    def clear(self) -> None:
        self._contexts.clear()

    def _evict_if_needed(self) -> None:
        while len(self._contexts) > self._max_size:
            self._contexts.popitem(last=False)
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
