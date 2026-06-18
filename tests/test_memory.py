"""Vector memory tests."""

from likecodex_engine.memory.vector import VectorMemory


def test_memory_search_jsonl(tmp_path):
    mem = VectorMemory(tmp_path / "memory.jsonl")
    mem.add("python agent loop implementation")
    mem.add("rust sandbox docker executor")
    results = mem.search("agent loop")
    assert results
    assert "agent" in results[0]["text"]


def test_memory_types(tmp_path):
    mem = VectorMemory(tmp_path / "memory.jsonl")
    mem.add("user preference", memory_type="user")
    mem.add("project convention", memory_type="project")
    mem.add("reference doc", memory_type="reference")
    project = mem.list_by_type("project")
    assert len(project) == 1
    assert project[0]["metadata"]["type"] == "project"
    filtered = mem.search("convention", memory_type="project")
    assert len(filtered) == 1
