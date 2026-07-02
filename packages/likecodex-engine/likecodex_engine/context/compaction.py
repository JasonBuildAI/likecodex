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
DEFAULT_SOFT_COMPACT_RATIO = 0.5
DEFAULT_COMPACT_FORCE_RATIO = 0.9
DEFAULT_CONTEXT_WINDOW = 1_000_000
MAX_PINNED_USER_CHARS = 6000
MAX_CONSECUTIVE_NOOP_COMPACTS = 3


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
        soft_compact_ratio: float = DEFAULT_SOFT_COMPACT_RATIO,
        compact_force_ratio: float = DEFAULT_COMPACT_FORCE_RATIO,
        working_dir: str = ".",
    ) -> None:
        self.max_messages = max_messages
        self.context_window = context_window
        self.compact_ratio = compact_ratio
        self.soft_compact_ratio = soft_compact_ratio
        self.compact_force_ratio = compact_force_ratio
        self.working_dir = Path(working_dir)
        self._consecutive_noop_compacts = 0
        self._last_log_size = 0

    def should_compact(self, prompt_tokens: int) -> bool:
        threshold = int(self.context_window * self.compact_ratio)
        return prompt_tokens >= threshold

    def should_soft_compact(self, prompt_tokens: int) -> bool:
        """Return True when we should emit a soft notice (below hard threshold)."""
        threshold = int(self.context_window * self.soft_compact_ratio)
        return prompt_tokens >= threshold

    def should_force_compact(self, prompt_tokens: int) -> bool:
        """Return True when we must compact regardless of fold-economics."""
        threshold = int(self.context_window * self.compact_force_ratio)
        return prompt_tokens >= threshold

    def fold_economics(self, foldable: list[Message]) -> bool:
        """Skip compaction when folding would not reduce context meaningfully.

        Reasonix foldEconomics: if foldable is small relative to the total log,
        or if the summary would be nearly as large as the foldable content,
        skip the LLM call and archive-only pass.
        """
        if not foldable:
            return False
        total_chars = sum(len(m.content) for m in foldable)
        # If foldable is less than 500 chars, not worth the LLM call
        if total_chars < 500:
            return False
        # If foldable is less than 10% of the total log, skip
        if self._last_log_size > 0:
            ratio = total_chars / self._last_log_size
            if ratio < 0.1:
                return False
        return True

    def compact_stuck(self) -> bool:
        """Detect consecutive compactions that produce no reduction.

        Reasonix compactStuck: if we've compacted N times in a row without
        meaningful reduction, pause compaction to avoid a dead loop.
        """
        return self._consecutive_noop_compacts >= MAX_CONSECUTIVE_NOOP_COMPACTS

    def summarize_log(self, log: list[Message]) -> str:
        """Enhanced rule-based summary extracting decisions, errors, and progress."""
        user_msgs = [m for m in log if m.role == Role.USER]
        tool_msgs = [m for m in log if m.role == Role.TOOL]
        assistant_msgs = [m for m in log if m.role == Role.ASSISTANT]

        # Extract key decisions: user messages with decision indicators
        decision_kw = ["改为", "使用", "采用", "选择", "use", "choose", "select", "decide", "switch"]
        decisions = [
            m.content[:200] for m in user_msgs
            if any(kw in m.content.lower() for kw in decision_kw)
        ]

        # Extract errors from tool results
        errors = [
            m.content[:150] for m in tool_msgs
            if '"error"' in m.content.lower() or 'exit_code' in m.content.lower()
        ]

        # Extract final assistant messages (last 2)
        final_assistant = [m.content[:300] for m in assistant_msgs if m.content][-2:]

        parts = [f"{SUMMARY_TAG_OPEN}"]
        parts.append("Previous conversation summarized due to context limits.")
        parts.append(f"Turns: {len(assistant_msgs)} assistant, {len(tool_msgs)} tool results.")

        if decisions:
            parts.append("## Key Decisions\n- " + "\n- ".join(decisions[-3:]))

        if errors:
            parts.append("## Errors\n- " + "\n- ".join(errors[-3:]))

        if final_assistant:
            parts.append("## Last Output\n" + "\n".join(final_assistant))

        # Recent user intent (last user message)
        if user_msgs:
            last_user = user_msgs[-1].content[:150]
            parts.append(f"## Last User Request\n{last_user}")

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

    @staticmethod
    def _is_pinned(m: Message) -> bool:
        """Check if a user message should be pinned (not folded)."""
        if SUMMARY_TAG_OPEN in m.content:
            return True
        if m.content.startswith(CONTEXT_PREFIX):
            return True
        if len(m.content) > MAX_PINNED_USER_CHARS:
            return False
        if m.content.startswith("[Plan]\n"):
            return False
        return True

    def split_compactable(self, log: list[Message]) -> tuple[list[Message], list[Message]]:
        """Split pinned user turns vs foldable assistant/tool work."""
        pinned: list[Message] = []
        foldable: list[Message] = []
        for m in log:
            if m.role == Role.USER and self._is_pinned(m):
                pinned.append(m)
            else:
                foldable.append(m)
        return pinned, foldable

    def emergency_trim(self, log: list[Message]) -> list[Message]:
        if len(log) <= self.max_messages:
            return log
        return log[-self.max_messages :]
