"""Prune stale tool results before LLM compaction."""

from __future__ import annotations

from dataclasses import dataclass

from likecodex_engine.llm.base import Message, Role

PRUNED_MARKER = "[elided tool result — "
MIN_PRUNE_BYTES = 1024
ERROR_PREFIXES = ("error:", "blocked:", "[loop guard]")


@dataclass
class PruneStats:
    results: int = 0
    saved_chars: int = 0


def _is_error_message(content: str) -> bool:
    lower = content.lower().strip()
    return any(lower.startswith(prefix) for prefix in ERROR_PREFIXES)


def _is_error_message(content: str) -> bool:
    lower = content.lower().strip()
    return any(lower.startswith(prefix) for prefix in ERROR_PREFIXES)


def _is_duplicate_tool_result(log: list[Message], idx: int) -> bool:
    """Check if this tool result is a duplicate of a nearby one."""
    msg = log[idx]
    if msg.role != Role.TOOL:
        return False
    content = (msg.content or "")[:200]
    # Compare with nearby tool results
    for j in range(max(0, idx - 5), idx):
        other = log[j]
        if other.role == Role.TOOL and (other.content or "")[:200] == content:
            return True
    return False


def merge_consecutive_messages(log: list[Message]) -> list[Message]:
    """Merge consecutive user+assistant turns into single entries."""
    if len(log) < 2:
        return log
    merged = [log[0]]
    for i in range(1, len(log)):
        prev = merged[-1]
        curr = log[i]
        # Merge consecutive assistant messages
        if prev.role == Role.ASSISTANT and curr.role == Role.ASSISTANT:
            merged[-1] = Message(
                role=prev.role,
                content=(prev.content or "") + "\n" + (curr.content or ""),
                tool_call_id=prev.tool_call_id,
            )
            continue
        merged.append(curr)
    return merged


def prune_stale_tool_results(log: list[Message], *, tail_keep: int = 8) -> tuple[list[Message], PruneStats]:
    """Elide large tool results outside the protected tail."""
    stats = PruneStats()
    if len(log) <= tail_keep:
        return log, stats

    cutoff = len(log) - tail_keep
    next_log = list(log)
    for idx in range(cutoff):
        msg = next_log[idx]
        if msg.role != Role.TOOL:
            continue
        content = msg.content or ""
        if len(content) < MIN_PRUNE_BYTES or content.startswith(PRUNED_MARKER):
            continue
        if _is_error_message(content):
            continue
        placeholder = (
            f"{PRUNED_MARKER}{len(content)} bytes dropped to save context; re-run the tool if the data is needed again]"
        )
        stats.saved_chars += len(content) - len(placeholder)
        next_log[idx] = Message(
            role=msg.role,
            content=placeholder,
            tool_call_id=msg.tool_call_id,
        )
        stats.results += 1
    return next_log, stats
