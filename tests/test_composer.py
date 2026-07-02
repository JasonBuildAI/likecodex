"""Tests for Composer backend — sessions, diff engine, undo/redo.

Tests cover:
- Session creation and management (Phase 3.1)
- Diff generation and application (Phase 3.2)
- Undo/redo stack (Phase 3.5)
- Conflict detection
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from likecodex_engine.composer.manager import ComposerSession, SessionFile, SessionManager
from likecodex_engine.tools.diff_engine import (
    ChunkDiff,
    DiffOp,
    DiffResult,
    MyersDiff,
    apply_diff,
    apply_unified_diff,
    compute_diff,
    diff_stats,
    reverse_diff,
)
from likecodex_engine.tools.undo_stack import EditEntry, EditGroup, UndoStack


# ============================================================
# Phase 3.1: Session Management Tests
# ============================================================


class TestComposerSession:
    """Tests for ComposerSession dataclass."""

    def test_create_session(self) -> None:
        session = ComposerSession(session_id="test-1")
        assert session.session_id == "test-1"
        assert session.status == "active"
        assert session.created_at
        assert session.updated_at
        assert len(session.files) == 0

    def test_add_file(self) -> None:
        session = ComposerSession(session_id="test-2")
        sf = session.add_file("src/main.py", "old", "new", language="python")
        assert sf.file_path == "src/main.py"
        assert sf.original_content == "old"
        assert sf.modified_content == "new"
        assert sf.status == "pending"
        assert "src/main.py" in session.files

    def test_remove_file(self) -> None:
        session = ComposerSession(session_id="test-3")
        session.add_file("a.py", "old", "new")
        assert session.remove_file("a.py") is True
        assert session.remove_file("nonexistent.py") is False

    def test_file_lifecycle(self) -> None:
        session = ComposerSession(session_id="test-4")
        session.add_file("f.py", "old", "new")
        assert session.files["f.py"].status == "pending"
        assert session.pending_count() == 1

        session.accept_file("f.py")
        assert session.files["f.py"].status == "accepted"
        assert session.accepted_count() == 1
        assert session.pending_count() == 0

        session.reject_file("f.py")
        assert session.files["f.py"].status == "rejected"

    def test_serialization_roundtrip(self) -> None:
        session = ComposerSession(session_id="test-5")
        session.add_file("a.py", "old_a", "new_a", language="python")
        session.add_file("b.ts", "old_b", "new_b", language="typescript")
        session.accept_file("a.py")

        data = session.to_dict()
        restored = ComposerSession.from_dict(data)

        assert restored.session_id == "test-5"
        assert len(restored.files) == 2
        assert restored.files["a.py"].status == "accepted"
        assert restored.files["b.ts"].status == "pending"
        assert restored.files["a.py"].original_content == "old_a"
        assert restored.files["b.ts"].modified_content == "new_b"

    def test_summary(self) -> None:
        session = ComposerSession(session_id="test-6")
        session.add_file("x.py", "", "")
        summary = session.summary()
        assert summary["session_id"] == "test-6"
        assert summary["file_count"] == 1
        assert summary["pending"] == 1


class TestSessionManager:
    """Tests for SessionManager."""

    def test_create_and_get_session(self) -> None:
        mgr = SessionManager()
        session = mgr.create_session("sess-1")
        assert mgr.get_session("sess-1") is session
        assert mgr.get_session("nonexistent") is None

    def test_list_sessions(self) -> None:
        mgr = SessionManager()
        mgr.create_session("s1")
        mgr.create_session("s2")
        mgr.complete_session("s1")
        assert len(mgr.list_sessions()) == 2
        assert len(mgr.list_sessions(status="active")) == 1
        assert len(mgr.list_sessions(status="completed")) == 1

    def test_delete_session(self) -> None:
        mgr = SessionManager()
        mgr.create_session("s1")
        assert mgr.delete_session("s1") is True
        assert mgr.delete_session("nonexistent") is False
        assert mgr.get_session("s1") is None

    def test_add_file_to_session(self) -> None:
        mgr = SessionManager()
        mgr.create_session("s1")
        sf = mgr.add_file_to_session("s1", "f.py", "old", "new")
        assert sf is not None
        assert sf.file_path == "f.py"

        # Non-existent session
        assert mgr.add_file_to_session("bad", "f.py") is None

    def test_persistence(self, tmp_path: Path) -> None:
        mgr = SessionManager(storage_dir=str(tmp_path / "sessions"))
        mgr.create_session("persist-1")
        mgr.add_file_to_session("persist-1", "f.py", "old", "new")

        # Save
        assert mgr.save_session("persist-1") is True

        # Load into new manager
        mgr2 = SessionManager(storage_dir=str(tmp_path / "sessions"))
        loaded = mgr2.load_session("persist-1")
        assert loaded is not None
        assert loaded.session_id == "persist-1"
        assert "f.py" in loaded.files

    def test_save_all(self, tmp_path: Path) -> None:
        mgr = SessionManager(storage_dir=str(tmp_path / "sessions"))
        mgr.create_session("a")
        mgr.create_session("b")
        assert mgr.save_all() == 2

        mgr2 = SessionManager(storage_dir=str(tmp_path / "sessions"))
        assert mgr2.load_all() == 2
        assert mgr2.get_session("a") is not None
        assert mgr2.get_session("b") is not None


# ============================================================
# Phase 3.2: Diff Engine Tests
# ============================================================


class TestMyersDiff:
    """Tests for MyersDiff algorithm."""

    def test_no_changes(self) -> None:
        lines = ["line1", "line2", "line3"]
        result = MyersDiff.diff(lines, lines)
        assert result.net_changes == 0

    def test_insertion(self) -> None:
        old = ["a", "b"]
        new = ["a", "b", "c"]
        result = MyersDiff.diff(old, new)
        assert result.added == 1

    def test_deletion(self) -> None:
        old = ["a", "b", "c"]
        new = ["a", "b"]
        result = MyersDiff.diff(old, new)
        assert result.removed == 1

    def test_replace(self) -> None:
        old = ["a", "b", "c"]
        new = ["a", "x", "c"]
        result = MyersDiff.diff(old, new)
        assert result.net_changes > 0

    def test_empty_old(self) -> None:
        result = MyersDiff.diff([], ["a", "b"])
        assert result.added == 2

    def test_empty_new(self) -> None:
        result = MyersDiff.diff(["a", "b"], [])
        assert result.removed == 2

    def test_identical_content(self) -> None:
        old = ["def foo():", "    pass", "", "def bar():", "    return 42"]
        new = ["def foo():", "    pass", "", "def bar():", "    return 42"]
        result = MyersDiff.diff(old, new)
        assert result.net_changes == 0

    def test_complex_diff(self) -> None:
        old = [
            "import os",
            "import sys",
            "",
            "def main():",
            "    print('hello')",
            "",
            "if __name__ == '__main__':",
            "    main()",
        ]
        new = [
            "import os",
            "import sys",
            "import json",
            "",
            "def main():",
            "    name = os.getenv('NAME', 'world')",
            "    print(f'hello {name}')",
            "",
            "if __name__ == '__main__':",
            "    main()",
        ]
        result = MyersDiff.diff(old, new)
        assert result.net_changes > 0
        assert result.added > 0


class TestDiffResult:
    """Tests for DiffResult operations."""

    def test_unified_diff_format(self) -> None:
        old = ["a", "b", "c"]
        new = ["a", "x", "c"]
        result = MyersDiff.diff(old, new)
        udiff = result.to_unified_diff("a/file", "b/file")
        assert "--- a/file" in udiff
        assert "+++ b/file" in udiff
        assert "-b" in udiff
        assert "+x" in udiff

    def test_diff_stats(self) -> None:
        old = ["a", "b", "c", "d"]
        new = ["a", "x", "c"]
        result = MyersDiff.diff(old, new)
        stats = diff_stats(result)
        assert "added" in stats
        assert "removed" in stats
        assert stats["total"] > 0


class TestChunkDiff:
    """Tests for ChunkDiff."""

    def test_split_chunks_python(self) -> None:
        lines = [
            "import os",
            "",
            "def foo():",
            "    pass",
            "",
            "def bar():",
            "    return 1",
        ]
        chunks = ChunkDiff.split_chunks(lines)
        assert len(chunks) >= 2  # header + foo + bar
        names = [name for name, _ in chunks]
        assert any("def foo" in name for name in names)

    def test_chunk_diff_no_changes(self) -> None:
        lines = ["def a():", "    pass", "", "def b():", "    return 2"]
        result = ChunkDiff.diff(lines, lines)
        assert result.net_changes == 0

    def test_chunk_diff_with_change(self) -> None:
        old = ["def a():", "    return 1", "", "def b():", "    return 2"]
        new = ["def a():", "    return 1", "", "def b():", "    return 42"]
        result = ChunkDiff.diff(old, new)
        assert result.net_changes > 0


class TestDiffApplication:
    """Tests for apply_diff and reverse_diff."""

    def test_apply_simple_diff(self) -> None:
        old_text = "line1\nline2\nline3\n"
        ops = [
            DiffOp(
                tag="replace",
                old_start=1,
                old_end=2,
                new_start=1,
                new_end=2,
                content=["line2", "line_modified"],
            ),
        ]
        result = apply_diff(old_text, ops)
        assert result is not None
        assert "line_modified" in result
        assert "line1" in result
        assert "line3" in result

    def test_apply_insertion(self) -> None:
        old_text = "a\nb\n"
        ops = [
            DiffOp(
                tag="insert",
                old_start=2,
                old_end=2,
                new_start=2,
                new_end=3,
                content=["c"],
            ),
        ]
        result = apply_diff(old_text, ops)
        assert result is not None
        lines = result.splitlines()
        assert lines == ["a", "b", "c"]

    def test_reverse_diff(self) -> None:
        ops = [
            DiffOp(
                tag="replace",
                old_start=0,
                old_end=1,
                new_start=0,
                new_end=1,
                content=["old", "new"],
            ),
        ]
        reversed_ops = reverse_diff(ops)
        assert len(reversed_ops) == 1
        assert reversed_ops[0].tag == "replace"
        assert reversed_ops[0].old_start == 0
        assert reversed_ops[0].new_start == 0

    def test_apply_unified_diff(self) -> None:
        original = "def foo():\n    return 1\n"
        patch = "@@ -1,2 +1,2 @@\n def foo():\n-    return 1\n+    return 42\n"
        result = apply_unified_diff(original, patch)
        assert result is not None
        assert "return 42" in result
        assert "return 1" not in result

    def test_compute_diff_function(self) -> None:
        old = "a\nb\nc\n"
        new = "a\nx\nc\n"
        result = compute_diff(old, new, algorithm="myers")
        assert result.net_changes > 0

        result_chunk = compute_diff(old, new, algorithm="chunk")
        assert result_chunk is not None


# ============================================================
# Phase 3.5: Undo/Redo Tests
# ============================================================


class TestUndoStack:
    """Tests for UndoStack."""

    def test_push_and_undo(self) -> None:
        stack = UndoStack(max_depth=10)
        stack.push("f.py", "old", "new", "edit f.py")
        assert stack.can_undo()
        assert not stack.can_redo()

        group = stack.undo()
        assert group is not None
        assert len(group.edits) == 1
        assert group.edits[0].before_content == "old"
        assert group.edits[0].after_content == "new"
        assert group.edits[0].file_path == "f.py"

    def test_redo_after_undo(self) -> None:
        stack = UndoStack(max_depth=10)
        stack.push("f.py", "old", "new")
        stack.undo()

        assert stack.can_redo()
        group = stack.redo()
        assert group is not None
        assert group.edits[0].after_content == "new"

    def test_push_clears_redo(self) -> None:
        stack = UndoStack(max_depth=10)
        stack.push("f.py", "old", "new")
        stack.undo()
        stack.push("f.py", "new", "newer")
        # Redo should be cleared after new push
        assert not stack.can_redo()

    def test_undo_empty_stack(self) -> None:
        stack = UndoStack(max_depth=10)
        assert stack.undo() is None
        assert not stack.can_undo()

    def test_redo_empty_stack(self) -> None:
        stack = UndoStack(max_depth=10)
        assert stack.redo() is None

    def test_max_depth(self) -> None:
        stack = UndoStack(max_depth=3)
        for i in range(5):
            stack.push("f.py", str(i), str(i + 1))
        assert stack.undo_count == 3

    def test_push_group(self) -> None:
        stack = UndoStack(max_depth=10)
        edits = [
            EditEntry(file_path="a.py", before_content="old_a", after_content="new_a"),
            EditEntry(file_path="b.py", before_content="old_b", after_content="new_b"),
        ]
        stack.push_group(edits, "batch edit")
        assert stack.undo_count == 1

        group = stack.undo()
        assert group is not None
        assert len(group.edits) == 2
        assert group.affected_files == {"a.py", "b.py"}

    def test_noop_not_pushed(self) -> None:
        stack = UndoStack(max_depth=10)
        stack.push("f.py", "same", "same")  # No change
        assert stack.undo_count == 0

    def test_clear(self) -> None:
        stack = UndoStack(max_depth=10)
        stack.push("f.py", "old", "new")
        stack.clear()
        assert not stack.can_undo()
        assert not stack.can_redo()

    def test_peek(self) -> None:
        stack = UndoStack(max_depth=10)
        stack.push("f.py", "old", "new")
        peeked = stack.peek_undo()
        assert peeked is not None
        assert peeked.edits[0].before_content == "old"
        # Peek should not remove
        assert stack.undo_count == 1

    def test_session_scoping(self) -> None:
        stack = UndoStack(max_depth=50)
        s1 = stack.get_session_stack("session-1")
        s2 = stack.get_session_stack("session-2")

        s1.push("a.py", "old", "new")
        s2.push("b.py", "old", "new")

        assert s1.undo_count == 1
        assert s2.undo_count == 1
        assert s1.can_undo()
        assert not s1.can_redo()

    def test_get_undo_history(self) -> None:
        stack = UndoStack(max_depth=10)
        stack.push("f.py", "old", "new", "edit f")
        history = stack.get_undo_history()
        assert len(history) == 1
        assert history[0]["edits"][0]["file_path"] == "f.py"
        assert history[0]["description"] == "edit f"


class TestEditEntry:
    """Tests for EditEntry dataclass."""

    def test_create(self) -> None:
        entry = EditEntry(
            file_path="test.py",
            before_content="old",
            after_content="new",
            description="update test",
        )
        assert entry.file_path == "test.py"
        assert entry.before_content == "old"
        assert entry.after_content == "new"
        assert entry.timestamp
        assert not entry.is_noop

    def test_noop_detection(self) -> None:
        entry = EditEntry(file_path="f.py", before_content="same", after_content="same")
        assert entry.is_noop


class TestEditGroup:
    """Tests for EditGroup dataclass."""

    def test_create_and_add(self) -> None:
        group = EditGroup(description="batch")
        group.add_edit(EditEntry("a.py", "old", "new"))
        group.add_edit(EditEntry("b.py", "old", "new"))
        assert len(group.edits) == 2
        assert group.affected_files == {"a.py", "b.py"}

    def test_undo_order(self) -> None:
        group = EditGroup()
        group.add_edit(EditEntry("a.py", "old_a", "new_a"))
        group.add_edit(EditEntry("b.py", "old_b", "new_b"))
        undone = group.undo()
        assert len(undone) == 2
        # Reverse order
        assert undone[0].file_path == "b.py"


# ============================================================
# Phase 3.2: DiffResult edge cases
# ============================================================


class TestDiffEdgeCases:
    """Edge cases for diff operations."""

    def test_large_diff(self) -> None:
        old = [f"line_{i}" for i in range(100)]
        new = [f"line_{i}" if i != 50 else f"modified_{i}" for i in range(100)]
        result = MyersDiff.diff(old, new)
        assert result.net_changes > 0

    def test_unicode_content(self) -> None:
        old = ["你好", "世界"]
        new = ["你好", "LikeCodex"]
        result = MyersDiff.diff(old, new)
        assert result.net_changes > 0

    def test_empty_sequences(self) -> None:
        result = MyersDiff.diff([], [])
        assert result.net_changes == 0

    def test_conflict_detection(self) -> None:
        """Test that divergent edits produce detectable conflicts."""
        base = ["line1", "line2", "line3"]
        edit_a = ["line1", "line_a", "line3"]
        edit_b = ["line1", "line_b", "line3"]
        diff_a = MyersDiff.diff(base, edit_a)
        diff_b = MyersDiff.diff(base, edit_b)
        assert diff_a.net_changes > 0
        assert diff_b.net_changes > 0
        # The two diffs are different
        assert diff_a.to_unified_diff() != diff_b.to_unified_diff()

    def test_apply_diff_undo(self) -> None:
        """Test applying then reversing a diff returns to original."""
        original = "def foo():\n    return 1\n"
        modified = "def foo():\n    return 42\n"

        # Compute diff and apply
        result = compute_diff(original, modified)
        patched = apply_diff(original, result.ops)
        assert patched == modified

        # Reverse and apply
        reversed_ops = reverse_diff(result.ops)
        unpatched = apply_diff(modified, reversed_ops)
        assert unpatched == original
