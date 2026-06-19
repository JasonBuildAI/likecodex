"""History tool tests."""

import json

import pytest
from likecodex_engine.tools.history import HistoryTools


@pytest.mark.asyncio
async def test_history_search_empty(tmp_path):
    tools = HistoryTools(str(tmp_path))
    out = json.loads(await tools.history("compaction", scope="project"))
    assert "hits" in out


@pytest.mark.asyncio
async def test_history_search_finds_archive(tmp_path):
    archive = tmp_path / ".likecodex" / "archive"
    archive.mkdir(parents=True)
    (archive / "test.jsonl").write_text(
        '{"role":"user","content":"refactor login module with JWT tokens"}\n',
        encoding="utf-8",
    )
    tools = HistoryTools(str(tmp_path))
    out = json.loads(await tools.history("JWT login", scope="project"))
    assert len(out["hits"]) >= 1
