"""Symbol position helpers for LSP queries."""

from __future__ import annotations

import re
from pathlib import Path


def find_symbol_column(path: Path, line: int, symbol: str) -> int:
    """Return 0-based column for symbol on the given 1-based line."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0
    if line < 1 or line > len(lines):
        return 0
    text = lines[line - 1]
    match = re.search(rf"\b{re.escape(symbol)}\b", text)
    return match.start() if match else 0
