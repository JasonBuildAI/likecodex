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
    """Smart truncate oversized tool output.
    
    Preserves important lines (ERROR/WARNING/Exception/traceback) while
    applying head+tail truncation for the rest.
    Returns (body, user notice).
    """
    raw = result.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return result, ""
    
    # Try smart truncation: keep head + important lines + tail
    lines = result.split("\n")
    important_keywords = ("error", "warning", "exception", "traceback", "fail", "SyntaxError", "ImportError")
    important_lines = []
    head_count = max(5, len(lines) // 5)  # Keep first 20% or at least 5 lines
    tail_count = max(5, len(lines) // 5)  # Keep last 20% or at least 5 lines
    
    for i, line in enumerate(lines):
        if i < head_count:
            continue  # Already in head
        if i >= len(lines) - tail_count:
            continue  # Already in tail
        # Check if this is an important line
        if any(kw in line.lower() for kw in important_keywords):
            important_lines.append((i, line))
    
    # Build the preserved content
    keep = max_bytes // 2
    raw_head = raw[:keep]
    raw_tail = raw[-keep:]
    head = _snap_head(raw_head, keep)
    tail = _snap_tail(raw_tail, keep)
    
    important_text = ""
    if important_lines:
        important_text = "\n".join(line for _, line in important_lines[:10])
        if important_text:
            important_text = f"\n\n# --- Important lines ---\n{important_text}\n\n# --- End important lines ---\n"
    
    head_len = len(head.encode("utf-8", errors="replace"))
    tail_len = len(tail.encode("utf-8", errors="replace"))
    important_len = len(important_text.encode("utf-8", errors="replace"))
    total_kept = head_len + tail_len + important_len
    omitted = max(0, len(raw) - total_kept)
    notice = f"tool output truncated: {omitted} of {len(raw)} bytes elided"
    body = (
        head
        + f"\n\n…[truncated {omitted} of {len(raw)} bytes — {len(important_lines)} important lines preserved]…\n\n"
        + important_text
        + tail
    )
    return body, notice
