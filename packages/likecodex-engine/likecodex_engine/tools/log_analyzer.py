"""Log file analysis tools with large file support."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


_CHUNK_SIZE = 1 << 20  # 1 MiB


def _iter_lines(path: Path, encoding: str = "utf-8") -> list[str]:
    """Read all lines from a file, handling large files by reading in chunks."""
    lines: list[str] = []
    with path.open("rb") as f:
        leftover = b""
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            data = leftover + chunk
            parts = data.split(b"\n")
            leftover = parts[-1]
            for part in parts[:-1]:
                try:
                    lines.append(part.decode(encoding, errors="replace"))
                except Exception:
                    lines.append(part.decode("utf-8", errors="replace"))
        if leftover:
            try:
                lines.append(leftover.decode(encoding, errors="replace"))
            except Exception:
                lines.append(leftover.decode("utf-8", errors="replace"))
    return lines


_DEFAULT_PATTERNS = {
    "error": re.compile(r"(?i)\b(?:error|exception|fail(?:ure|ed)?|crash|fatal)\b"),
    "warning": re.compile(r"(?i)\b(?:warn(?:ing)?)\b"),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
}


class LogAnalyzerTools:
    """Tools for analyzing log files, searching patterns, and summarizing errors."""

    @staticmethod
    def analyze_log_schema() -> dict[str, Any]:
        return {
            "description": "Analyze a log file for error, warning, and traceback patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to the log file",
                    },
                    "patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Custom regex patterns to match (optional)",
                    },
                },
                "required": ["file"],
            },
        }

    @staticmethod
    def tail_schema() -> dict[str, Any]:
        return {
            "description": "Read the last N lines of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Path to the file"},
                    "lines": {
                        "type": "integer",
                        "default": 20,
                        "description": "Number of lines to show",
                    },
                },
                "required": ["file"],
            },
        }

    @staticmethod
    def grep_log_schema() -> dict[str, Any]:
        return {
            "description": "Search a log file for lines matching a regex pattern with surrounding context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Path to the log file"},
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "context": {
                        "type": "integer",
                        "default": 3,
                        "description": "Number of context lines before and after each match",
                    },
                },
                "required": ["file", "pattern"],
            },
        }

    @staticmethod
    def error_summary_schema() -> dict[str, Any]:
        return {
            "description": "Summarize errors in a log file grouped by unique error messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Path to the log file"},
                    "top_n": {
                        "type": "integer",
                        "default": 20,
                        "description": "Number of top errors to show",
                    },
                },
                "required": ["file"],
            },
        }

    async def analyze_log(
        self,
        file: str,
        patterns: list[str] | None = None,
    ) -> str:
        path = Path(file)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file}"})

        try:
            lines = _iter_lines(path)
            total_lines = len(lines)

            compiled_patterns: dict[str, re.Pattern] = {}
            if patterns:
                for p in patterns:
                    compiled_patterns[p] = re.compile(p)
            else:
                compiled_patterns = dict(_DEFAULT_PATTERNS)

            results: dict[str, list[dict[str, Any]]] = {}
            for name in compiled_patterns:
                results[name] = []

            for idx, line in enumerate(lines):
                for name, pattern in compiled_patterns.items():
                    if pattern.search(line):
                        results[name].append({"line": idx + 1, "text": line.rstrip()})

            summary = {
                k: {"count": len(v), "matches": v[:20]}
                for k, v in results.items()
            }
            return json.dumps({
                "file": file,
                "total_lines": total_lines,
                "results": summary,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def tail(self, file: str, lines: int = 20) -> str:
        path = Path(file)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file}"})

        try:
            all_lines = _iter_lines(path)
            tail_lines = all_lines[-lines:]
            return json.dumps({
                "file": file,
                "total_lines": len(all_lines),
                "showing": len(tail_lines),
                "lines": tail_lines,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def grep_log(
        self,
        file: str,
        pattern: str,
        context: int = 3,
    ) -> str:
        path = Path(file)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file}"})

        try:
            compiled = re.compile(pattern)
            all_lines = _iter_lines(path)
            matches: list[dict[str, Any]] = []

            for idx, line in enumerate(all_lines):
                if compiled.search(line):
                    start = max(0, idx - context)
                    end = min(len(all_lines), idx + context + 1)
                    context_lines = [
                        {"line": i + 1, "text": all_lines[i].rstrip()}
                        for i in range(start, end)
                    ]
                    matches.append({
                        "line": idx + 1,
                        "text": line.rstrip(),
                        "context": context_lines,
                    })
                    if len(matches) >= 100:  # safety limit
                        break

            return json.dumps({
                "file": file,
                "pattern": pattern,
                "matches_count": len(matches),
                "matches": matches,
            })
        except re.error as e:
            return json.dumps({"error": f"Invalid regex: {e}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def error_summary(self, file: str, top_n: int = 20) -> str:
        path = Path(file)
        if not path.exists():
            return json.dumps({"error": f"File not found: {file}"})

        try:
            error_pattern = _DEFAULT_PATTERNS["error"]
            all_lines = _iter_lines(path)
            matched_lines: list[str] = []
            for line in all_lines:
                if error_pattern.search(line):
                    matched_lines.append(line.strip())

            counter: Counter = Counter()
            for line in matched_lines:
                # Normalize variable parts
                normalized = re.sub(r"\b\d+\b", "N", line)
                normalized = re.sub(r'"[^"]*"', '"..."', normalized)
                normalized = re.sub(r"'[^']*'", "'...'", normalized)
                counter[normalized] += 1

            top = counter.most_common(top_n)
            return json.dumps({
                "file": file,
                "total_error_lines": len(matched_lines),
                "unique_error_groups": len(counter),
                "top_errors": [
                    {"count": count, "pattern": pattern}
                    for pattern, count in top
                ],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
