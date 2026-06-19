"""LSP tool smoke tests."""

import json

import pytest
from likecodex_engine.tools.lsp_tools import LspSemanticTools


@pytest.mark.asyncio
async def test_lsp_definition_no_server(tmp_path):
    tools = LspSemanticTools(str(tmp_path))
    (tmp_path / "main.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    out = json.loads(await tools.lsp_definition("main.py", 1, "foo"))
    assert "error" in out or "definitions" in out


@pytest.mark.asyncio
async def test_lsp_diagnostics_fallback(tmp_path):
    tools = LspSemanticTools(str(tmp_path))
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    out = json.loads(await tools.lsp_diagnostics("."))
    assert "diagnostics" in out or "error" in out or "tool" in out
