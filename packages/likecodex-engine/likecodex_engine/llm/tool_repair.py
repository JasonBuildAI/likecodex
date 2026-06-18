"""Tool-call repair pipeline for DeepSeek reliability."""

from __future__ import annotations

import json
import re
from typing import Any

from likecodex_engine.context.utils import stable_json_dumps
from likecodex_engine.llm.base import LLMResponse, ToolCall


def flatten_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested JSON Schema for DeepSeek tool parameter stability."""
    if not isinstance(schema, dict):
        return schema
    props = schema.get("properties", {})
    if not props:
        return schema
    flat_props: dict[str, Any] = {}
    for key, value in sorted(props.items()):
        if isinstance(value, dict) and "properties" in value:
            inner = value.get("properties", {})
            for inner_key, inner_val in sorted(inner.items()):
                flat_props[f"{key}_{inner_key}"] = inner_val
        else:
            flat_props[key] = value
    return {
        "type": "object",
        "properties": flat_props,
        "required": schema.get("required", []),
    }


def flatten_tool_schemas(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") != "function":
            out.append(tool)
            continue
        fn = tool.get("function", {})
        params = fn.get("parameters", {})
        out.append(
            {
                "type": "function",
                "function": {
                    **fn,
                    "parameters": flatten_schema(params) if isinstance(params, dict) else params,
                },
            }
        )
    return out


def repair_json(text: str) -> dict[str, Any]:
    """Best-effort JSON repair for truncated tool arguments."""
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # trailing comma
    cleaned = re.sub(r",\s*}", "}", text)
    cleaned = re.sub(r",\s*]", "]", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # truncate to last complete brace
    if "{" in text:
        depth = 0
        last_good = 0
        for i, ch in enumerate(text):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    last_good = i + 1
        if last_good:
            try:
                return json.loads(text[:last_good])
            except json.JSONDecodeError:
                pass
    return {}


def repair_tool_call(tc: ToolCall) -> ToolCall:
    if isinstance(tc.arguments, dict):
        return tc
    if isinstance(tc.arguments, str):
        return ToolCall(id=tc.id, name=tc.name, arguments=repair_json(tc.arguments))
    return tc


def repair_tool_calls(response: LLMResponse) -> LLMResponse:
    if not response.tool_calls:
        return response
    repaired = [repair_tool_call(tc) for tc in response.tool_calls]
    return response.model_copy(update={"tool_calls": repaired})


def scavenge_tool_calls_from_text(content: str) -> list[ToolCall]:
    """Extract tool calls leaked into assistant text."""
    found: list[ToolCall] = []
    pattern = re.compile(
        r'"name"\s*:\s*"([a-zA-Z0-9_]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})',
        re.DOTALL,
    )
    for idx, match in enumerate(pattern.finditer(content)):
        name = match.group(1)
        args = repair_json(match.group(2))
        found.append(ToolCall(id=f"scavenged_{idx}", name=name, arguments=args))
    return found


def merge_tool_calls(response: LLMResponse) -> LLMResponse:
    """Merge scavenged calls and dedupe by name within same turn."""
    scavenged = scavenge_tool_calls_from_text(response.content)
    if not scavenged:
        return repair_tool_calls(response)
    seen = {tc.name for tc in response.tool_calls}
    merged = list(response.tool_calls)
    for tc in scavenged:
        if tc.name not in seen:
            merged.append(tc)
            seen.add(tc.name)
    return repair_tool_calls(response.model_copy(update={"tool_calls": merged}))


def stable_tool_schemas_for_api(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = flatten_tool_schemas(tools)
    return json.loads(stable_json_dumps(flattened))
