"""Inline completion service — provides AI-powered code completion (Tab to accept)."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from likecodex_engine.llm.base import LLMProvider, Message, Role

logger = logging.getLogger(__name__)


@dataclass
class InlineCompletionRequest:
    """Request for inline code completion."""

    file_path: str = ""
    language: str = "plaintext"
    prefix: str = ""
    suffix: str = ""
    imports: list[str] = field(default_factory=list)
    current_scope: str = ""
    cursor_line: int = 0
    cursor_col: int = 0


@dataclass
class InlineCompletionResult:
    """Result of an inline completion request."""

    text: str
    completion_id: str
    model: str
    latency_ms: int
    cache_hit: bool = False


COMPLETION_SYSTEM = """You are an expert code completion assistant. Complete the code at the cursor position marked by <CURSOR>.
Rules:
1. Return ONLY the completion text that should be inserted at the cursor position.
2. Do NOT repeat any of the prefix or suffix.
3. Match the indentation style of the surrounding code.
4. Keep completions concise — typically 1-5 lines.
5. Do NOT wrap the completion in markdown code blocks.
6. Do NOT include any explanation or comments unless the user's code style uses them."""


class InlineCompletionService:
    """Provides AI-powered inline code completions."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm = llm_provider
        self._cache: dict[str, tuple[float, str]] = {}
        self._cache_ttl = 3.0  # cache valid for 3 seconds

    def _make_cache_key(self, request: InlineCompletionRequest) -> str:
        content = f"{request.file_path}:{request.cursor_line}:{request.cursor_col}:{request.prefix[-120:]}"
        return hashlib.md5(content.encode()).hexdigest()

    def _check_cache(self, key: str) -> str | None:
        if key in self._cache:
            ts, text = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return text
            del self._cache[key]
        return None

    def _set_cache(self, key: str, text: str) -> None:
        self._cache[key] = (time.time(), text)
        # Simple eviction: keep cache under 100 entries
        if len(self._cache) > 100:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]

    def _build_prompt(self, request: InlineCompletionRequest) -> str:
        parts: list[str] = []
        if request.imports:
            parts.append("Imports:\n" + "\n".join(request.imports))
        if request.current_scope:
            parts.append(f"Current scope: {request.current_scope}")

        parts.append(f"File: {request.file_path}")
        parts.append(f"Language: {request.language}")
        parts.append("Context (cursor marked as <CURSOR>):")
        parts.append(f"```{request.language}\n{request.prefix}<CURSOR>{request.suffix}\n```")
        parts.append("Complete the code at <CURSOR>. Return only the insertion:")

        return "\n\n".join(parts)

    async def complete(
        self,
        request: InlineCompletionRequest,
        llm: LLMProvider | None = None,
    ) -> InlineCompletionResult | None:
        """Generate an inline completion for the given context."""
        start = time.time()

        # 1. Check cache
        cache_key = self._make_cache_key(request)
        cached = self._check_cache(cache_key)
        if cached:
            return InlineCompletionResult(
                text=cached,
                completion_id=cache_key,
                model="cache",
                latency_ms=0,
                cache_hit=True,
            )

        # 2. Build prompt
        prompt = self._build_prompt(request)

        # 3. Call LLM
        provider = llm or self._llm
        if provider is None:
            logger.warning("No LLM provider available for completion")
            return None

        try:
            messages = [
                Message(role=Role.SYSTEM, content=COMPLETION_SYSTEM),
                Message(role=Role.USER, content=prompt),
            ]
            response = await provider.complete(
                messages=messages,
                temperature=0.1,
                max_tokens=256,
            )
            text = response.content.strip()

            # Clean up: remove markdown code block wrapper if present
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            if not text:
                return None

            # 4. Cache result
            self._set_cache(cache_key, text)

            latency = int((time.time() - start) * 1000)
            return InlineCompletionResult(
                text=text,
                completion_id=cache_key,
                model=response.model or "unknown",
                latency_ms=latency,
            )
        except Exception as e:
            logger.warning(f"Inline completion failed: {e}")
            return None
