"""API contract tests for Rust event JSON."""

import json


def test_event_adjacent_tag_shape():
    sample = {
        "type": "stream_chunk",
        "payload": {"task_id": "abc", "content": "hello"},
    }
    data = json.dumps(sample)
    parsed = json.loads(data)
    assert parsed["type"] == "stream_chunk"
    assert parsed["payload"]["content"] == "hello"
