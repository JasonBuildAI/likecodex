"""Vector memory tests."""

from likecodex_engine.memory.vector import VectorMemory


def test_memory_search_jsonl(tmp_path):
    mem = VectorMemory(tmp_path / "memory.jsonl")
    mem.add("python agent loop implementation")
    mem.add("rust sandbox docker executor")
    results = mem.search("agent loop")
    assert results
    assert "agent" in results[0]["text"]
