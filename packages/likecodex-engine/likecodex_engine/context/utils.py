"""Shared context utilities."""

from __future__ import annotations

import json
from typing import Any

DEFAULT_SYSTEM_PROMPT_PATH = "prompts/system.md"
CONTEXT_PREFIX = "[Context]\n"


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_tool_calls_json(calls: list[dict[str, Any]]) -> str:
    return stable_json_dumps(calls)
