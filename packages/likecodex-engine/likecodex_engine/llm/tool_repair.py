"""Tool-call repair pipeline for DeepSeek reliability."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from likecodex_engine.context.utils import stable_json_dumps
from likecodex_engine.llm.base import LLMResponse, Message, Role, ToolCall

INTERRUPTED_TOOL_RESULT = "[no result: the previous turn was interrupted before this tool call completed]"


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


def ensure_tool_call_ids(tool_calls: list[ToolCall]) -> list[ToolCall]:
    """Assign stable ids to tool calls missing them before persistence.
    Also detects and fixes duplicate IDs by appending a unique suffix.
    """
    out: list[ToolCall] = []
    used_ids: set[str] = set()
    global _CROSS_TURN_IDS
    for idx, tc in enumerate(tool_calls):
        tid = tc.id
        if not tid:
            tid = f"call_{uuid.uuid4().hex}"
        elif tid in used_ids:
            tid = f"call_{uuid.uuid4().hex}"
        elif tid in _CROSS_TURN_IDS:
            tid = f"{tid}_{uuid.uuid4().hex[:4]}"
        used_ids.add(tid)
        _CROSS_TURN_IDS.add(tid)
        out.append(tc.model_copy(update={"id": tid}))
    return out


# Cross-turn ID registry to detect conflicts across iterations
_CROSS_TURN_IDS: set[str] = set()


def reset_tool_call_id_registry() -> None:
    """Reset the cross-turn tool call ID registry."""
    _CROSS_TURN_IDS.clear()


def validate_tool_call_ids(tool_calls: list[ToolCall]) -> list[str]:
    """Pre-validate tool call IDs and return list of issues found.
    Checks: missing IDs, duplicates, non-standard format.
    Returns list of warning messages (empty if all valid).
    """
    issues: list[str] = []
    seen: set[str] = set()
    for idx, tc in enumerate(tool_calls):
        if not tc.id:
            issues.append(f"Tool call {idx} ({tc.name}): missing ID")
        elif tc.id in seen:
            issues.append(f"Tool call {idx} ({tc.name}): duplicate ID '{tc.id}'")
        seen.add(tc.id)
    return issues


def stable_tool_schemas_for_api(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = flatten_tool_schemas(tools)
    return json.loads(stable_json_dumps(flattened))


def _tool_call_id(tc: dict[str, Any]) -> str:
    return str(tc.get("id") or "")


def _get_fn(tc: dict[str, Any]) -> dict[str, Any]:
    return tc.get("function") or {}


def _tool_call_name(tc: dict[str, Any]) -> str:
    return str(_get_fn(tc).get("name") or "")


def _tool_call_args(tc: dict[str, Any]) -> str:
    args = _get_fn(tc).get("arguments", "{}")
    if isinstance(args, dict):
        return stable_json_dumps(args)
    return str(args or "{}")


def _id_distinct(calls: list[dict[str, Any]]) -> bool:
    seen: set[str] = set()
    for tc in calls:
        call_id = _tool_call_id(tc)
        if not call_id or call_id in seen:
            return False
        seen.add(call_id)
    return True


def close_truncated_json(text: str) -> str:
    """Best-effort completion for JSON cut off mid-stream."""
    stack: list[str] = []
    in_str = False
    escaped = False
    for ch in text:
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]" and stack:
            stack.pop()
    out = text
    if escaped:
        out = out[:-1]
    if in_str:
        out += '"'
    trimmed = out.rstrip(" \t\r\n")
    if trimmed.endswith(","):
        out = trimmed[:-1]
    elif trimmed.endswith(":"):
        out = trimmed + "null"
    out += "".join(reversed(stack))
    try:
        json.loads(out)
        return out
    except json.JSONDecodeError:
        return "{}"


def _repair_tool_call_dicts(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    for tc in calls:
        args = _tool_call_args(tc)
        if args and args != "{}":
            try:
                json.loads(args)
            except json.JSONDecodeError:
                args = close_truncated_json(args)
        fn = dict(tc.get("function") or {})
        fn["arguments"] = args
        repaired.append({**tc, "function": fn})
    return repaired


def _backfill_tool_call_names(calls: list[dict[str, Any]], results: list[Message]) -> list[dict[str, Any]]:
    if not any(not _tool_call_name(tc) for tc in calls):
        return calls
    out = [dict(tc) for tc in calls]
    if _id_distinct(calls):
        by_id = {r.tool_call_id or "": r.name or "" for r in results if r.name}
        for tc in out:
            if not _tool_call_name(tc):
                name = by_id.get(_tool_call_id(tc), "")
                if name:
                    tc.setdefault("function", {})["name"] = name
        return out
    for idx, tc in enumerate(out):
        if not _tool_call_name(tc) and idx < len(results) and results[idx].name:
            tc.setdefault("function", {})["name"] = results[idx].name or ""
    return out


def _interrupted_msg(call_id: str, name: str | None) -> Message:
    return Message(
        role=Role.TOOL,
        content=INTERRUPTED_TOOL_RESULT,
        tool_call_id=call_id,
        name=name,
    )


def _pair_tool_results(calls: list[dict[str, Any]], avail: list[Message]) -> list[Message]:
    out: list[Message] = []
    if _id_distinct(calls):
        by_id = {r.tool_call_id or "": r for r in avail}
        for tc in calls:
            call_id = _tool_call_id(tc)
            if call_id in by_id:
                out.append(by_id[call_id])
            else:
                out.append(_interrupted_msg(call_id, _tool_call_name(tc) or None))
        return out
    for idx, tc in enumerate(calls):
        call_id = _tool_call_id(tc)
        if idx < len(avail):
            result = avail[idx].model_copy(update={"tool_call_id": call_id or avail[idx].tool_call_id})
            out.append(result)
        else:
            out.append(_interrupted_msg(call_id, _tool_call_name(tc) or None))
    return out


def sanitize_tool_pairing(messages: list[Message]) -> list[Message]:
    """Repair tool-call / tool-result pairing before sending to the LLM API."""
    out: list[Message] = []
    i = 0
    while i < len(messages):
        message = messages[i]
        if message.role == Role.ASSISTANT and message.tool_calls:
            j = i + 1
            while j < len(messages) and messages[j].role == Role.TOOL:
                j += 1
            calls = (
                json.loads(message.raw_tool_calls)
                if message.raw_tool_calls
                else list(message.tool_calls)
            )
            calls = _backfill_tool_call_names(calls, messages[i + 1 : j])
            calls = _repair_tool_call_dicts(calls)
            assistant = message.model_copy(update={"tool_calls": calls})
            out.append(assistant)
            out.extend(_pair_tool_results(calls, messages[i + 1 : j]))
            i = j
            continue
        if message.role == Role.TOOL:
            i += 1
            continue
        out.append(message.model_copy(deep=True))
        i += 1
    return out
