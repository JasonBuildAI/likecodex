"""Tests for merged configuration loading."""

from __future__ import annotations

from pathlib import Path

from likecodex_engine.config_loader import load_merged_config, project_config_paths


def test_project_config_paths_order(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    sub = root / "sub"
    sub.mkdir(parents=True)
    (root / "likecodex.toml").write_text('[llm]\nmodel = "root-model"\n', encoding="utf-8")
    (sub / "likecodex.toml").write_text('[llm]\nmodel = "sub-model"\n', encoding="utf-8")

    paths = project_config_paths(sub)
    assert len(paths) == 2
    merged = load_merged_config(sub)
    assert merged["llm"]["model"] == "sub-model"
