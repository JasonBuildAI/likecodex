"""Tests for the Skills CRUD manager module."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

from likecodex_engine.skills.manager import (
    create_skill,
    delete_skill,
    export_skill,
    import_skill,
    update_skill,
    validate_skill_name,
)


class TestValidateSkillName:
    def test_valid_names(self):
        assert validate_skill_name("my-skill") is None
        assert validate_skill_name("debug") is None
        assert validate_skill_name("a") is None
        assert validate_skill_name("my-cool-skill-123") is None
        assert validate_skill_name("a" * 64) is None

    def test_invalid_names(self):
        assert validate_skill_name("") is not None
        assert validate_skill_name("-starts-with-hyphen") is not None
        assert validate_skill_name("UPPERCASE") is not None
        assert validate_skill_name("has spaces") is not None
        assert validate_skill_name("a" * 65) is not None
        assert validate_skill_name("special!chars") is not None


class TestCreateSkill:
    def test_create_basic_skill(self, tmp_path: Path):
        skill_md = create_skill(
            tmp_path,
            "test-skill",
            description="A test skill",
            body="Do something useful.",
        )
        assert skill_md.exists()
        assert skill_md.name == "SKILL.md"
        assert skill_md.parent.name == "test-skill"
        content = skill_md.read_text(encoding="utf-8")
        assert "name: test-skill" in content
        assert "description:" in content
        assert "Do something useful." in content

    def test_create_with_all_fields(self, tmp_path: Path):
        skill_md = create_skill(
            tmp_path,
            "full-skill",
            description="Full featured",
            body="Body text",
            run_as="subagent",
            model="deepseek-v4-pro",
            allowed_tools=["read_file", "write_file"],
            author="Test Author",
            version="1.0.0",
        )
        content = skill_md.read_text(encoding="utf-8")
        assert "runAs: subagent" in content
        assert "model: deepseek-v4-pro" in content
        assert "allowed-tools:" in content
        assert "author: Test Author" in content
        assert "version: 1.0.0" in content

    def test_create_invalid_name_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Invalid name"):
            create_skill(tmp_path, "INVALID", description="bad")

    def test_create_skill_creates_directory(self, tmp_path: Path):
        create_skill(tmp_path, "new-skill", description="test")
        skill_dir = tmp_path / ".likecodex" / "skills" / "new-skill"
        assert skill_dir.is_dir()


class TestUpdateSkill:
    def test_update_description(self, tmp_path: Path):
        create_skill(tmp_path, "upd-skill", description="Old desc", body="Body")
        result = update_skill(tmp_path, "upd-skill", description="New desc")
        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "New desc" in content

    def test_update_body(self, tmp_path: Path):
        create_skill(tmp_path, "upd-skill", description="Desc", body="Old body")
        result = update_skill(tmp_path, "upd-skill", body="New body text")
        assert result is not None
        content = result.read_text(encoding="utf-8")
        assert "New body text" in content

    def test_update_nonexistent_returns_none(self, tmp_path: Path):
        result = update_skill(tmp_path, "no-such-skill", description="test")
        assert result is None


class TestDeleteSkill:
    def test_delete_existing_skill(self, tmp_path: Path):
        create_skill(tmp_path, "del-skill", description="To be deleted")
        ok = delete_skill(tmp_path, "del-skill")
        assert ok is True
        assert not (tmp_path / ".likecodex" / "skills" / "del-skill").exists()

    def test_delete_nonexistent_returns_false(self, tmp_path: Path):
        ok = delete_skill(tmp_path, "no-such-skill")
        assert ok is False


class TestExportImport:
    def test_export_skill(self, tmp_path: Path):
        create_skill(tmp_path, "exp-skill", description="Export me", body="Export body")
        data = export_skill(tmp_path, "exp-skill")
        assert isinstance(data, bytes)
        assert len(data) > 0
        # Verify it's a valid zip
        import io
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            assert "SKILL.md" in names

    def test_import_skill(self, tmp_path: Path):
        # Create a zip in memory
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("imp-skill/SKILL.md", "---\nname: imp-skill\n---\nImported body")
        names = import_skill(tmp_path, buf.getvalue())
        assert "imp-skill" in names
        imported = tmp_path / ".likecodex" / "skills" / "imp-skill" / "SKILL.md"
        assert imported.exists()

    def test_export_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            export_skill(tmp_path, "no-such")
