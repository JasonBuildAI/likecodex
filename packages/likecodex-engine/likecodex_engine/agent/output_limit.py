"""Cap tool output size before it enters the model context."""

from __future__ import annotations

MAX_TOOL_OUTPUT_BYTES = 32 * 1024


def _snap_head(data: bytes, keep: int) -> str:
    return data[:keep].decode("utf-8", errors="ignore")


def _snap_tail(data: bytes, keep: int) -> str:
    start = max(0, len(data) - keep)
    for skip in range(4):
        try:
            return data[start + skip :].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return data[start:].decode("utf-8", errors="replace")


def limit_tool_output(result: str, max_bytes: int = MAX_TOOL_OUTPUT_BYTES) -> tuple[str, str]:
    """Head+tail truncate oversized tool output; return (body, user notice)."""
    raw = result.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return result, ""
    keep = max_bytes // 2
    head = _snap_head(raw, keep)
    tail = _snap_tail(raw, keep)
    head_len = len(head.encode("utf-8", errors="replace"))
    tail_len = len(tail.encode("utf-8", errors="replace"))
    omitted = max(0, len(raw) - head_len - tail_len)
    notice = f"tool output truncated: {omitted} of {len(raw)} bytes elided"
    body = (
        head
        + f"\n\n…[truncated {omitted} of {len(raw)} bytes — rerun with narrower args to see the middle]…\n\n"
        + tail
    )
    return body, notice
