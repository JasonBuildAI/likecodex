"""grep gitignore tests."""

import json

import pytest
from likecodex_engine.tools.code_search import CodeSearchTools


@pytest.mark.asyncio
async def test_grep_respects_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    ignored = tmp_path / "ignored"
    ignored.mkdir()
    (ignored / "secret.py").write_text("TODO secret\n", encoding="utf-8")
    (tmp_path / "visible.py").write_text("TODO visible\n", encoding="utf-8")
    search = CodeSearchTools(str(tmp_path))
    out = json.loads(await search.grep_files("TODO"))
    files = {r["file"].replace("\\", "/") for r in out["results"]}
    assert "visible.py" in files
    assert not any("ignored" in f for f in files)
