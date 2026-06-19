"""Tests for the code graph and diagnostics tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from likecodex_engine.tools.code_search import CodeSearchTools
from likecodex_engine.tools.codegraph import build_codegraph, load_or_build


def _seed(root: Path) -> None:
    (root / "pkg").mkdir()
    (root / "pkg" / "math_utils.py").write_text(
        "def add(a, b):\n    return a + b\n\n\nclass Calc:\n    def run(self):\n        return add(1, 2)\n",
        encoding="utf-8",
    )
    (root / "main.py").write_text(
        "from pkg.math_utils import add\n\n\ndef main():\n    print(add(3, 4))\n",
        encoding="utf-8",
    )
    (root / "lib.ts").write_text(
        "export function greet(name: string) {\n  return `hi ${name}`;\n}\n\nexport class Greeter {}\n",
        encoding="utf-8",
    )


def test_build_codegraph_finds_symbols(tmp_path: Path) -> None:
    _seed(tmp_path)
    graph = build_codegraph(tmp_path)
    names = {(s.name, s.kind) for s in graph.symbols}
    assert ("add", "function") in names
    assert ("Calc", "class") in names
    assert ("main", "function") in names
    assert ("greet", "function") in names
    assert ("Greeter", "class") in names


def test_codegraph_records_references(tmp_path: Path) -> None:
    _seed(tmp_path)
    graph = build_codegraph(tmp_path)
    assert "add" in graph.references
    # add() is called in math_utils.py and main.py
    assert len(graph.references["add"]) >= 2


def test_load_or_build_caches(tmp_path: Path) -> None:
    _seed(tmp_path)
    graph = load_or_build(tmp_path)
    assert graph.file_count >= 3
    assert (tmp_path / ".likecodex" / "codegraph.json").exists()


@pytest.mark.asyncio
async def test_codegraph_search_tool(tmp_path: Path) -> None:
    _seed(tmp_path)
    tools = CodeSearchTools(str(tmp_path))
    res = json.loads(await tools.codegraph_search("add"))
    assert res["count"] >= 1
    assert res["results"][0]["name"] == "add"


@pytest.mark.asyncio
async def test_codegraph_symbols_tool(tmp_path: Path) -> None:
    _seed(tmp_path)
    tools = CodeSearchTools(str(tmp_path))
    res = json.loads(await tools.codegraph_symbols("pkg/math_utils.py"))
    names = {s["name"] for s in res["symbols"]}
    assert "add" in names and "Calc" in names


@pytest.mark.asyncio
async def test_codegraph_callers_tool(tmp_path: Path) -> None:
    _seed(tmp_path)
    tools = CodeSearchTools(str(tmp_path))
    res = json.loads(await tools.codegraph_callers("add"))
    assert res["count"] >= 2


@pytest.mark.asyncio
async def test_codegraph_reindex_tool(tmp_path: Path) -> None:
    _seed(tmp_path)
    tools = CodeSearchTools(str(tmp_path))
    res = json.loads(await tools.codegraph_reindex())
    assert res["reindexed"] is True
    assert res["symbols"] >= 4


@pytest.mark.asyncio
async def test_lsp_diagnostics_python(tmp_path: Path) -> None:
    from likecodex_engine.tools.lsp import LspTools

    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    tools = LspTools(str(tmp_path))
    res = json.loads(await tools.diagnostics("ok.py"))
    # Either a checker ran, or none was installed; both are valid outcomes.
    assert "language" in res and res["language"] == "python"
