"""Undo/Redo Stack — file edit history tracking with session scoping.

Tracks file edits with before/after content snapshots.
Supports undo(), redo(), configurable max history depth.
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EditEntry:
    """A single file edit entry in the undo stack."""

    file_path: str
    before_content: str
    after_content: str
    timestamp: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def is_noop(self) -> bool:
        return self.before_content == self.after_content


@dataclass
class EditGroup:
    """A group of edits applied atomically (one logical change)."""

    edits: list[EditEntry] = field(default_factory=list)
    timestamp: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def add_edit(self, edit: EditEntry) -> None:
        self.edits.append(edit)

    def undo(self) -> list[EditEntry]:
        """Return edits in reverse order to undo this group."""
        return list(reversed(self.edits))

    @property
    def affected_files(self) -> set[str]:
        return {e.file_path for e in self.edits}


class UndoStack:
    """Thread-safe undo/redo stack for file edits.

    Configurable maximum depth. Supports session scoping so that
    different composer sessions have independent undo histories.
    """

    def __init__(self, max_depth: int = 50) -> None:
        self._max_depth = max_depth
        self._undo: deque[EditGroup] = deque(maxlen=max_depth)
        self._redo: deque[EditGroup] = deque(maxlen=max_depth)
        self._session_stacks: dict[str, UndoStack] = {}

    # ── Core operations ──────────────────────────────────────────────

    def push(self, file_path: str, before: str, after: str, description: str = "") -> None:
        """Push a single file edit onto the undo stack.

        Clears the redo stack (new branch of history).
        """
        if before == after:
            return

        entry = EditEntry(
            file_path=file_path,
            before_content=before,
            after_content=after,
            description=description,
        )
        group = EditGroup(edits=[entry], description=description)
        self._undo.append(group)
        self._redo.clear()

    def push_group(self, edits: list[EditEntry], description: str = "") -> None:
        """Push a group of edits as one atomic undo unit."""
        if not edits:
            return

        group = EditGroup(edits=list(edits), description=description)
        self._undo.append(group)
        self._redo.clear()

    def undo(self) -> EditGroup | None:
        """Undo the last edit group.

        Returns:
            The undone EditGroup, or None if nothing to undo.
        """
        if not self._undo:
            return None

        group = self._undo.pop()
        self._redo.append(group)
        return group

    def redo(self) -> EditGroup | None:
        """Redo the last undone edit group.

        Returns:
            The redone EditGroup, or None if nothing to redo.
        """
        if not self._redo:
            return None

        group = self._redo.pop()
        self._undo.append(group)
        return group

    # ── State management ─────────────────────────────────────────────

    def can_undo(self) -> bool:
        return len(self._undo) > 0

    def can_redo(self) -> bool:
        return len(self._redo) > 0

    def clear(self) -> None:
        """Clear undo and redo stacks."""
        self._undo.clear()
        self._redo.clear()

    @property
    def undo_count(self) -> int:
        return len(self._undo)

    @property
    def redo_count(self) -> int:
        return len(self._redo)

    def peek_undo(self) -> EditGroup | None:
        """Peek at the last undo entry without removing it."""
        if not self._undo:
            return None
        return self._undo[-1]

    def peek_redo(self) -> EditGroup | None:
        """Peek at the last redo entry without removing it."""
        if not self._redo:
            return None
        return self._redo[-1]

    # ── Session scoping ──────────────────────────────────────────────

    def get_session_stack(self, session_id: str) -> UndoStack:
        """Get or create a session-scoped undo stack.

        Allows independent undo/redo per composer session.
        """
        if session_id not in self._session_stacks:
            self._session_stacks[session_id] = UndoStack(max_depth=self._max_depth)
        return self._session_stacks[session_id]

    def clear_session_stack(self, session_id: str) -> None:
        """Clear undo/redo state for a specific session."""
        if session_id in self._session_stacks:
            del self._session_stacks[session_id]

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize undo stack state (for persistence)."""
        return {
            "max_depth": self._max_depth,
            "undo": [
                {
                    "edits": [
                        {
                            "file_path": e.file_path,
                            "before_content": e.before_content,
                            "after_content": e.after_content,
                            "timestamp": e.timestamp,
                            "description": e.description,
                        }
                        for e in g.edits
                    ],
                    "timestamp": g.timestamp,
                    "description": g.description,
                }
                for g in self._undo
            ],
            "redo": [
                {
                    "edits": [
                        {
                            "file_path": e.file_path,
                            "before_content": e.before_content,
                            "after_content": e.after_content,
                            "timestamp": e.timestamp,
                            "description": e.description,
                        }
                        for e in g.edits
                    ],
                    "timestamp": g.timestamp,
                    "description": g.description,
                }
                for g in self._redo
            ],
        }

    def get_undo_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent undo history for display.

        Args:
            limit: Max number of entries to return.

        Returns:
            List of dicts with file_path, description, timestamp.
        """
        history = []
        for g in list(self._undo)[-limit:]:
            history.append({
                "edits": [
                    {
                        "file_path": e.file_path,
                        "description": e.description,
                        "timestamp": e.timestamp,
                    }
                    for e in g.edits
                ],
                "description": g.description,
                "timestamp": g.timestamp,
            })
        return list(reversed(history))
