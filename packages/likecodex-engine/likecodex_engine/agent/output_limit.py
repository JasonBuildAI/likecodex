"""Cap tool output size before it enters the model context.

Three-tier truncation strategy:
  Tier 1: Short truncation (< 2x limit) — head + tail only
  Tier 2: Medium truncation (< 5x limit) — head + important lines + tail
  Tier 3: Deep truncation (>= 5x limit) — ERROR lines only + aggressive head+tail
"""

from __future__ import annotations

import re

MAX_TOOL_OUTPUT_BYTES = 32 * 1024
ERROR_KEYWORDS = ("error", "exception", "traceback", "fail", "SyntaxError", "ImportError")
IMPORTANT_KEYWORDS = ERROR_KEYWORDS + ("warning", "exit_code", "stderr")


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


def _is_error_line(line: str) -> bool:
    return any(kw in line.lower() for kw in ERROR_KEYWORDS)


def _tier1_truncate(lines: list[str], max_bytes: int, raw: bytes) -> tuple[str, str]:
    """Tier 1: head + tail only."""
    keep = max_bytes // 2
    raw_head = raw[:keep]
    raw_tail = raw[-keep:]
    head = _snap_head(raw_head, keep)
    tail = _snap_tail(raw_tail, keep)
    head_len = len(head.encode("utf-8", errors="replace"))
    tail_len = len(tail.encode("utf-8", errors="replace"))
    omitted = max(0, len(raw) - head_len - tail_len)
    notice = f"tool output truncated: {omitted} of {len(raw)} bytes elided (tier 1)"
    body = head + f"\n\n…[truncated {omitted} bytes]…\n\n" + tail
    return body, notice


def _tier2_truncate(lines: list[str], max_bytes: int, raw: bytes) -> tuple[str, str]:
    """Tier 2: head + important lines + tail."""
    keep = max_bytes // 2
    raw_head = raw[:keep]
    raw_tail = raw[-keep:]
    head = _snap_head(raw_head, keep)
    tail = _snap_tail(raw_tail, keep)

    # Collect important lines from the middle section
    head_count = max(5, len(lines) // 5)
    tail_count = max(5, len(lines) // 5)
    important_lines: list[str] = []
    for i, line in enumerate(lines):
        if i < head_count or i >= len(lines) - tail_count:
            continue
        if _is_error_line(line):
            important_lines.append(line)

    important_text = ""
    if important_lines:
        important_text = "\n".join(important_lines[:10])
        if important_text:
            important_text = f"\n\n# --- Error lines ---\n{important_text}\n\n# --- End error lines ---\n"

    head_len = len(head.encode("utf-8", errors="replace"))
    tail_len = len(tail.encode("utf-8", errors="replace"))
    important_len = len(important_text.encode("utf-8", errors="replace"))
    total_kept = head_len + tail_len + important_len
    omitted = max(0, len(raw) - total_kept)
    notice = f"tool output truncated: {omitted} of {len(raw)} bytes elided (tier 2)"
    body = (
        head
        + f"\n\n…[truncated {omitted} bytes — {len(important_lines)} error lines preserved]…\n\n"
        + important_text
        + tail
    )
    return body, notice


def _tier3_truncate(lines: list[str], max_bytes: int, raw: bytes) -> tuple[str, str]:
    """Tier 3: ERROR lines only + minimal context."""
    # Collect ALL error lines
    error_lines: list[str] = []
    for i, line in enumerate(lines):
        if _is_error_line(line):
            error_lines.append(line)

    # Also capture full last N lines for context
    tail_context = max(5, len(lines) // 10)
    tail_section = "\n".join(lines[-tail_context:])

    error_text = "\n".join(error_lines[:20]) if error_lines else ""
    error_block = f"# --- All error lines ({len(error_lines)}) ---\n{error_text}\n# --- End errors ---" if error_text else ""

    # Build compact output
    parts: list[str] = []
    if error_block:
        parts.append(error_block)
    parts.append(f"# --- Last {tail_context} lines ---\n{tail_section}")

    out = "\n\n".join(parts)
    out_bytes = out.encode("utf-8", errors="replace")
    if len(out_bytes) > max_bytes:
        out = _snap_head(out_bytes, max_bytes)

    omitted = max(0, len(raw) - len(out.encode("utf-8", errors="replace")))
    notice = f"tool output aggressively truncated: {omitted} of {len(raw)} bytes elided (tier 3)"
    return out, notice


def limit_tool_output(result: str, max_bytes: int = MAX_TOOL_OUTPUT_BYTES) -> tuple[str, str]:
    """Smart truncate oversized tool output using three-tier strategy.
    
    Tier 1 (< 2x limit): head + tail
    Tier 2 (< 5x limit): head + ERROR lines + tail
    Tier 3 (>= 5x limit): ERROR lines only + last N lines
    
    Returns (body, user notice).
    """
    raw = result.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return result, ""
    
    lines = result.split("\n")
    size_ratio = len(raw) / max_bytes
    
    if size_ratio < 2:
        return _tier1_truncate(lines, max_bytes, raw)
    elif size_ratio < 5:
        return _tier2_truncate(lines, max_bytes, raw)
    else:
        return _tier3_truncate(lines, max_bytes, raw)
