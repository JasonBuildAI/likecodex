"""read_file window tests."""

import json

import pytest
from likecodex_engine.tools.filesystem import FileSystemTools


@pytest.mark.asyncio
async def test_read_file_offset_limit(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("\n".join(f"line {i}" for i in range(1, 101)), encoding="utf-8")
    fs = FileSystemTools(str(tmp_path))
    out = json.loads(await fs.read_file("big.txt", offset=10, limit=3))
    assert "10→line 10" in out["content"]
    assert out["total_lines"] == 100
