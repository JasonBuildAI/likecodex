"""LLM compaction + archive for cache-reset points."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from likecodex_engine.context.utils import CONTEXT_PREFIX
from likecodex_engine.llm.base import Message, Role

if TYPE_CHECKING:
    from likecodex_engine.llm.base import LLMProvider

SUMMARY_TAG_OPEN = "<compaction-summary>"
SUMMARY_TAG_CLOSE = "</compaction-summary>"

SUMMARY_SYSTEM = """You are compacting a coding agent conversation. Write under these headings (omit empty):
## Standing facts & constraints
## Goal
## Decisions & rationale
## Files & code
## Commands & outcomes
## Errors & fixes
## Pending & next step
Be terse. Preserve paths and identifiers exactly."""

DEFAULT_COMPACT_RATIO = 0.8
DEFAULT_CONTEXT_WINDOW = 1_000_000
MAX_PINNED_USER_CHARS = 6000


class ContextCompactor:
    """Legacy tail-only compactor (deprecated)."""

    def __init__(self, max_messages: int = 100, max_tokens: int = 60000) -> None:
        self.max_messages = max_messages
        self.max_tokens = max_tokens

    def compact(self, messages: list[Message]) -> list[Message]:
        if not messages:
            return messages
        system = messages[0] if messages[0].role == Role.SYSTEM else None
        body = messages[1:] if system else list(messages)
        while len(body) + (1 if system else 0) > self.max_messages:
            if body:
                body.pop(0)
            else:
                break
        out: list[Message] = []
        if system:
            out.append(system)
        out.extend(body)
        return out


class CacheFirstCompactor:
    """Low-frequency compaction at cache-reset points."""

    def __init__(
        self,
        max_messages: int = 200,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        compact_ratio: float = DEFAULT_COMPACT_RATIO,
        working_dir: str = ".",
    ) -> None:
        self.max_messages = max_messages
        self.context_window = context_window
        self.compact_ratio = compact_ratio
        self.working_dir = Path(working_dir)

    def should_compact(self, prompt_tokens: int) -> bool:
        threshold = int(self.context_window * self.compact_ratio)
        return prompt_tokens >= threshold

    def summarize_log(self, log: list[Message]) -> str:
        """Rule-based fallback summary."""
        user_msgs = [m.content[:120] for m in log if m.role == Role.USER][-3:]
        tool_count = sum(1 for m in log if m.role == Role.TOOL)
        assistant_count = sum(1 for m in log if m.role == Role.ASSISTANT)
        parts = [
            f"{SUMMARY_TAG_OPEN}",
            "Previous conversation summarized due to context limits.",
            f"Turns: {assistant_count} assistant, {tool_count} tool results.",
        ]
        if user_msgs:
            parts.append("Recent user goals: " + " | ".join(user_msgs))
        parts.append(SUMMARY_TAG_CLOSE)
        return "\n".join(parts)

    async def llm_summarize(
        self,
        log: list[Message],
        llm: LLMProvider,
        *,
        instructions: str = "",
    ) -> str:
        """Structured LLM summary using deepseek-v4-flash."""
        lines: list[str] = []
        for m in log:
            role = m.role.value
            content = m.content[:4000]
            if m.role == Role.TOOL:
                lines.append(f"[tool result]: {content[:2000]}")
            else:
                lines.append(f"[{role}]: {content}")
        transcript = "\n".join(lines[-80:])
        user_content = f"Compact this transcript:\n\n{transcript}"
        if instructions.strip():
            user_content = f"Focus when summarizing: {instructions.strip()}\n\n{user_content}"
        messages = [
            Message(role=Role.SYSTEM, content=SUMMARY_SYSTEM),
            Message(role=Role.USER, content=user_content),
        ]
        resp = await llm.complete(messages, tools=None, temperature=0.0, max_tokens=4096)
        body = (resp.content or "").strip()
        if not body:
            return self.summarize_log(log)
        return f"{SUMMARY_TAG_OPEN}\n{body}\n{SUMMARY_TAG_CLOSE}"

    def archive_messages(self, log: list[Message]) -> Path | None:
        if not log:
            return None
        archive_dir = self.working_dir / ".likecodex" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = archive_dir / f"{ts}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for m in log:
                row = {
                    "role": m.role.value,
                    "content": m.content,
                    "tool_call_id": m.tool_call_id,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path

    def split_compactable(self, log: list[Message]) -> tuple[list[Message], list[Message]]:
        """Split pinned user turns vs foldable assistant/tool work."""
        pinned: list[Message] = []
        foldable: list[Message] = []
        for m in log:
            if m.role == Role.USER:
                if SUMMARY_TAG_OPEN in m.content or (
                    len(m.content) <= MAX_PINNED_USER_CHARS
                    and not m.content.startswith("[Plan]\n")
                    and not m.content.startswith(CONTEXT_PREFIX)
                ) or m.content.startswith(CONTEXT_PREFIX) and SUMMARY_TAG_OPEN in m.content:
                    pinned.append(m)
                else:
                    foldable.append(m)
            else:
                foldable.append(m)
        return pinned, foldable

    def emergency_trim(self, log: list[Message]) -> list[Message]:
        if len(log) <= self.max_messages:
            return log
        return log[-self.max_messages :]
