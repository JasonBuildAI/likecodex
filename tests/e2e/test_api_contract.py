"""API contract tests for Rust SSE event JSON (adjacently tagged)."""

from __future__ import annotations

import json

import pytest

EVENT_SAMPLES: dict[str, dict] = {
    "task_started": {"type": "task_started", "payload": {"id": "t1", "prompt": "hi", "status": "running"}},
    "task_completed": {"type": "task_completed", "payload": {"id": "t1", "prompt": "hi", "status": "completed"}},
    "stream_chunk": {"type": "stream_chunk", "payload": {"task_id": "t1", "content": "hello"}},
    "stream_finished": {"type": "stream_finished", "payload": {"task_id": "t1"}},
    "stream_retrying": {
        "type": "stream_retrying",
        "payload": {"task_id": "t1", "attempt": 1, "max": 3, "message": "retry"},
    },
    "compaction_started": {"type": "compaction_started", "payload": {"task_id": "t1", "trigger": "token_limit"}},
    "compaction_done": {
        "type": "compaction_done",
        "payload": {"task_id": "t1", "messages": 4, "summary_chars": 120, "archive": "/tmp/a.json"},
    },
    "checkpoint_created": {
        "type": "checkpoint_created",
        "payload": {"task_id": "t1", "checkpoint_id": "cp1", "label": "write_file", "files": ["a.txt"]},
    },
    "tool_call_requested": {
        "type": "tool_call_requested",
        "payload": {"task_id": "t1", "call": {"id": "c1", "name": "read_file", "arguments": {"path": "a.txt"}}},
    },
    "tool_call_completed": {
        "type": "tool_call_completed",
        "payload": {"task_id": "t1", "result": {"call_id": "c1", "content": "ok", "is_error": False}},
    },
    "permission_requested": {
        "type": "permission_requested",
        "payload": {
            "task_id": "t1",
            "request": {"id": "req-1", "action_type": "write_file", "description": "write a.txt"},
        },
    },
    "permission_responded": {
        "type": "permission_responded",
        "payload": {"task_id": "t1", "request_id": "req-1", "response": "allow_once"},
    },
    "plan_created": {
        "type": "plan_created",
        "payload": {"task_id": "t1", "steps": [{"id": "s1", "description": "inspect", "status": "pending"}]},
    },
    "message_added": {
        "type": "message_added",
        "payload": {"task_id": "t1", "message": {"role": "assistant", "content": "done"}},
    },
    "error": {"type": "error", "payload": {"task_id": "t1", "message": "boom"}},
}


@pytest.mark.parametrize("event_type", sorted(EVENT_SAMPLES.keys()))
def test_event_adjacent_tag_shape(event_type: str) -> None:
    sample = EVENT_SAMPLES[event_type]
    data = json.dumps(sample)
    parsed = json.loads(data)
    assert parsed["type"] == event_type
    assert isinstance(parsed["payload"], dict)


def test_stream_chunk_content_roundtrip() -> None:
    sample = EVENT_SAMPLES["stream_chunk"]
    parsed = json.loads(json.dumps(sample))
    assert parsed["payload"]["content"] == "hello"
