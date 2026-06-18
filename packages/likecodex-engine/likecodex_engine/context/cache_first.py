"""Cache-first context model: ImmutablePrefix + AppendOnlyLog + VolatileScratch."""

from __future__ import annotations

import hashlib
import importlib.resources as pkg_resources
import json
from dataclasses import dataclass, field
from typing import Any

from likecodex_engine.context.compaction import CacheFirstCompactor
from likecodex_engine.context.utils import CONTEXT_PREFIX, DEFAULT_SYSTEM_PROMPT_PATH, stable_tool_calls_json
from likecodex_engine.llm.base import Message, Role

PLAN_PREFIX = "[Plan]\n"
DEFAULT_CONTEXT_WINDOW = 1_000_000
DEFAULT_COMPACT_RATIO = 0.8


def _default_system_prompt() -> str:
    try:
        return pkg_resources.files("likecodex_engine").joinpath(DEFAULT_SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")
    except Exception:
        return "You are LikeCodex, a DeepSeek-powered software engineering agent."


@dataclass
class ImmutablePrefix:
    """Byte-stable prefix pinned for the session."""

    system_content: str
    skills_content: str = ""
    project_memories: str = ""

    @property
    def combined(self) -> str:
        parts = [self.system_content]
        if self.skills_content:
            parts.append(f"## Skills\n{self.skills_content}")
        if self.project_memories:
            parts.append(f"## Project Memory\n{self.project_memories}")
        return "\n\n".join(parts)

    def hash(self) -> str:
        return hashlib.sha256(self.combined.encode("utf-8")).hexdigest()


@dataclass
class VolatileScratch:
    """Transient state never sent to the LLM."""

    entries: list[str] = field(default_factory=list)

    def add(self, content: str) -> None:
        self.entries.append(content)

    def clear(self) -> None:
        self.entries.clear()


class CacheFirstContext:
    """Three-region context optimized for DeepSeek prefix caching."""

    def __init__(
        self,
        system_prompt: str | None = None,
        skills_content: str = "",
        max_messages: int = 200,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        compact_ratio: float = DEFAULT_COMPACT_RATIO,
        messages: list[Message] | None = None,
    ) -> None:
        self.prefix = ImmutablePrefix(
            system_content=system_prompt if system_prompt is not None else _default_system_prompt(),
            skills_content=skills_content,
        )
        self.scratch = VolatileScratch()
        self.compactor = CacheFirstCompactor(
            max_messages=max_messages,
            context_window=context_window,
            compact_ratio=compact_ratio,
        )
        self.last_prompt_tokens = 0
        self.cache_reset_count = 0

        if messages is not None:
            self._log: list[Message] = list(messages)
        else:
            self._log = []

    @property
    def messages(self) -> list[Message]:
        """Compatibility: flat message list including SYSTEM."""
        return [Message(role=Role.SYSTEM, content=self.prefix.combined), *self._log]

    def prefix_hash(self) -> str:
        return self.prefix.hash()

    def set_skills_content(self, content: str) -> None:
        self.prefix.skills_content = content

    def set_project_memories(self, content: str) -> None:
        self.prefix.project_memories = content

    def add_scratch(self, content: str) -> None:
        self.scratch.add(content)

    def add_user_message(self, content: str) -> None:
        self._log.append(Message(role=Role.USER, content=content))

    def add_context_block(self, content: str) -> None:
        block = content if content.startswith(CONTEXT_PREFIX) else f"{CONTEXT_PREFIX}{content}"
        self._log.append(Message(role=Role.USER, content=block))

    def add_plan_block(self, content: str) -> None:
        block = content if content.startswith(PLAN_PREFIX) else f"{PLAN_PREFIX}{content}"
        self._log.append(Message(role=Role.USER, content=block))

    def add_system_note(self, content: str) -> None:
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
        self._log.append(
            Message(
                role=Role.ASSISTANT,
                content=content,
                tool_calls=tool_calls,
                raw_tool_calls=serialized,
            )
        )

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self._log.append(Message(role=Role.TOOL, content=content, tool_call_id=tool_call_id))

    def record_prompt_tokens(self, usage: dict[str, int] | None) -> None:
        if not usage:
            return
        self.last_prompt_tokens = int(usage.get("prompt_tokens", self.last_prompt_tokens))
        if self.compactor.should_compact(self.last_prompt_tokens):
            self._compact()

    def _compact(self) -> None:
        summary = self.compactor.summarize_log(self._log)
        self._log = [Message(role=Role.USER, content=f"{CONTEXT_PREFIX}{summary}")]
        self.cache_reset_count += 1

    def build_for_llm(self) -> list[Message]:
        out: list[Message] = [Message(role=Role.SYSTEM, content=self.prefix.combined)]
        for message in self._log:
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

    def get_messages(self) -> list[Message]:
        return self.build_for_llm()

    def estimate_tokens(self) -> int:
        total = len(self.prefix.combined) // 4
        for m in self._log:
            total += len(m.content) // 4
            if m.raw_tool_calls:
                total += len(m.raw_tool_calls) // 4
        return total
