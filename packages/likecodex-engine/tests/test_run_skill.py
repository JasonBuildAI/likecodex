"""Tests for the Skill runner and loader modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from likecodex_engine.skills.loader import (
    Skill,
    discover_skills,
    inject_dynamic_context,
    skills_prefix_block,
    _parse_frontmatter,
    _parse_allowed_tools,
    _infer_source_type,
)
from likecodex_engine.skills.state import (
    load_skill_state,
    save_skill_state,
    is_skill_enabled,
    set_skill_enabled,
)


class TestSkillDataclass:
    def test_to_dict(self):
        skill = Skill(
            name="test",
            description="A test",
            body="Body",
            path=Path("/tmp/test.md"),
            source_dir=Path("/tmp"),
        )
        d = skill.to_dict()
        assert d["name"] == "test"
        assert "test.md" in d["path"]
        assert d["source_dir"] is not None
        assert d["source"] == "project"

    def test_source_property(self):
        skill = Skill(name="t", description="t", body="t", source_type="builtin")
        assert skill.source == "builtin"


class TestParseFrontmatter:
    def test_basic_yaml(self):
        text = '---\nname: test\ndescription: "A test skill"\n---\nBody text'
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "test"
        assert meta["description"] == "A test skill"
        assert body == "Body text"

    def test_no_frontmatter(self):
        text = "Just a body with no frontmatter"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_nested_metadata(self):
        text = '---\nname: test\nmetadata:\n  key1: val1\n  key2: val2\n---\nBody'
        meta, body = _parse_frontmatter(text)
        assert meta["metadata"]["key1"] == "val1"

    def test_allowed_tools_list(self):
        text = "---\nname: test\nallowed-tools:\n  - read_file\n  - write_file\n---\nBody"
        meta, body = _parse_frontmatter(text)
        tools = _parse_allowed_tools(meta.get("allowed-tools"))
        assert tools == ["read_file", "write_file"]


class TestParseAllowedTools:
    def test_string_input(self):
        assert _parse_allowed_tools("read_file write_file") == ["read_file", "write_file"]

    def test_list_input(self):
        assert _parse_allowed_tools(["read_file", "write_file"]) == ["read_file", "write_file"]

    def test_empty_input(self):
        assert _parse_allowed_tools("") == []
        assert _parse_allowed_tools(None) == []


class TestInferSourceType:
    def test_builtin(self):
        assert _infer_source_type(Path("/pkg/skills/builtins/test.md")) == "builtin"

    def test_home(self):
        home = str(Path.home())
        assert _infer_source_type(Path(f"{home}/skills/test.md")) == "home"

    def test_project(self):
        assert _infer_source_type(Path("/workspace/.likecodex/skills/test.md")) == "project"


class TestDiscoverSkills:
    def test_discovers_builtins(self, tmp_path: Path):
        skills = discover_skills(tmp_path)
        names = [s.name for s in skills]
        # Should find at least some built-in skills
        assert len(skills) > 0

    def test_disabled_skills_excluded(self, tmp_path: Path):
        skills = discover_skills(tmp_path, disabled=["explore"])
        names = [s.name for s in skills]
        assert "explore" not in names


class TestSkillsPrefixBlock:
    def test_empty_list(self):
        assert skills_prefix_block([]) == ""

    def test_skips_disabled(self):
        skills = [
            Skill(name="a", description="desc a", body="", enabled=True),
            Skill(name="b", description="desc b", body="", enabled=False),
        ]
        result = skills_prefix_block(skills)
        assert "**a**" in result
        assert "**b**" not in result


class TestInjectDynamicContext:
    def test_no_injection(self):
        body = "No dynamic content here"
        assert inject_dynamic_context(body) == body

    def test_command_injection(self):
        body = "Version: !`echo 1.0.0`"
        result = inject_dynamic_context(body)
        assert "1.0.0" in result

    def test_timeout_handling(self):
        body = "Slow: !`sleep 30`"
        result = inject_dynamic_context(body)
        assert "[error:" in result


class TestSkillState:
    def test_load_empty_state(self, tmp_path: Path):
        state = load_skill_state(tmp_path)
        assert state == {}

    def test_save_and_load(self, tmp_path: Path):
        state = {"test-skill": {"enabled": False}}
        save_skill_state(tmp_path, state)
        loaded = load_skill_state(tmp_path)
        assert loaded == state

    def test_is_skill_enabled_default(self, tmp_path: Path):
        assert is_skill_enabled(tmp_path, "unknown") is True

    def test_set_and_check_enabled(self, tmp_path: Path):
        set_skill_enabled(tmp_path, "my-skill", False)
        assert is_skill_enabled(tmp_path, "my-skill") is False
        set_skill_enabled(tmp_path, "my-skill", True)
        assert is_skill_enabled(tmp_path, "my-skill") is True
