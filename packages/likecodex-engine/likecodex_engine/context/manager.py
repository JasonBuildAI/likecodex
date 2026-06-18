"""Context / conversation management optimized for DeepSeek prefix caching."""

from __future__ import annotations

from likecodex_engine.context.cache_first import CacheFirstContext
from likecodex_engine.context.utils import (
    CONTEXT_PREFIX,
    DEFAULT_SYSTEM_PROMPT_PATH,
    stable_json_dumps,
    stable_tool_calls_json,
)
from likecodex_engine.llm.base import Message

ContextManager = CacheFirstContext

__all__ = [
    "CONTEXT_PREFIX",
    "CacheFirstContext",
    "ContextManager",
    "DEFAULT_SYSTEM_PROMPT_PATH",
    "stable_json_dumps",
    "stable_tool_calls_json",
    "Message",
]
