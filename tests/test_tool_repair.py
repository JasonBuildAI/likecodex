"""Tests for tool-call repair pipeline."""

from __future__ import annotations

from likecodex_engine.llm.base import LLMResponse, Message, Role, ToolCall
from likecodex_engine.llm.tool_repair import (
    INTERRUPTED_TOOL_RESULT,
    close_truncated_json,
    flatten_schema,
    merge_tool_calls,
    repair_json,
    sanitize_tool_pairing,
    scavenge_tool_calls_from_text,
)


def test_flatten_nested_schema() -> None:
    schema = {
        "type": "object",
        "properties": {
            "opts": {"type": "object", "properties": {"flag": {"type": "boolean"}}},
            "path": {"type": "string"},
        },
    }
    flat = flatten_schema(schema)
    assert "opts_flag" in flat["properties"]
    assert "path" in flat["properties"]


def test_repair_json_trailing_comma() -> None:
    assert repair_json('{"a": 1,}') == {"a": 1}


def test_repair_tool_call_string_args() -> None:
    from likecodex_engine.llm.tool_repair import repair_tool_call

    tc = repair_tool_call(ToolCall(id="1", name="read_file", arguments=repair_json('{"path": "x.py",}')))
    assert tc.arguments == {"path": "x.py"}


def test_scavenge_leaked_tool_call() -> None:
    text = 'Here is the call: {"name": "list_dir", "arguments": {"path": "."}}'
    found = scavenge_tool_calls_from_text(text)
    assert len(found) == 1
    assert found[0].name == "list_dir"


def test_merge_dedupes_by_name() -> None:
    response = LLMResponse(
        content='{"name": "grep_files", "arguments": {"pattern": "foo"}}',
        model="mock",
        tool_calls=[ToolCall(id="1", name="grep_files", arguments={"pattern": "foo"})],
    )
    merged = merge_tool_calls(response)
    names = [tc.name for tc in merged.tool_calls]
    assert names.count("grep_files") == 1


def test_close_truncated_json() -> None:
    assert close_truncated_json('{"path": "x.py"') == '{"path": "x.py"}'


def test_sanitize_backfills_unanswered_tool_call() -> None:
    messages = [
        Message(role=Role.USER, content="go"),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "echo", "arguments": "{}"},
                }
            ],
        ),
        Message(role=Role.USER, content="continue"),
    ]
    out = sanitize_tool_pairing(messages)
    tool_msgs = [m for m in out if m.role == Role.TOOL]
    assert len(tool_msgs) == 1
    assert INTERRUPTED_TOOL_RESULT in tool_msgs[0].content


def test_sanitize_pairs_empty_ids_by_position() -> None:
    messages = [
        Message(role=Role.USER, content="go"),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "echo", "arguments": '{"text":"alpha"}'},
                },
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "echo", "arguments": '{"text":"beta"}'},
                },
            ],
        ),
        Message(role=Role.TOOL, content='{"text":"alpha"}', tool_call_id=""),
        Message(role=Role.TOOL, content='{"text":"beta"}', tool_call_id=""),
    ]
    out = sanitize_tool_pairing(messages)
    tool_msgs = [m for m in out if m.role == Role.TOOL]
    assert len(tool_msgs) == 2
    assert tool_msgs[0].content != tool_msgs[1].content
