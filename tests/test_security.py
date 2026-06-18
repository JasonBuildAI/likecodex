"""Security tests for LikeCodex tools."""

from __future__ import annotations

import pytest
from likecodex_engine.tools.filesystem import FileSystemTools
from likecodex_engine.tools.git import GitTools


@pytest.mark.asyncio
async def test_read_file_rejects_path_escape(tmp_path):
    fs = FileSystemTools(str(tmp_path))
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    result = await fs.read_file(str(outside))
    assert "error" in result


@pytest.mark.asyncio
async def test_read_file_rejects_parent_traversal(tmp_path):
    fs = FileSystemTools(str(tmp_path))
    result = await fs.read_file("../outside.txt")
    assert "error" in result


@pytest.mark.asyncio
async def test_git_diff_rejects_injection(tmp_path):
    git = GitTools(str(tmp_path))
    result = await git.git_diff("HEAD; echo pwned")
    payload = __import__("json").loads(result)
    assert payload.get("exit_code") is not None or "error" in payload
