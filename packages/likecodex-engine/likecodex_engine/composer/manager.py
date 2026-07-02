"""Composer Session Management — session creation, persistence, file tracking.

ComposerSession tracks files being edited, pending changes, and session status.
Supports save/load for session persistence across agent restarts.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionFile:
    """A file tracked within a Composer session."""

    file_path: str
    original_content: str = ""
    modified_content: str = ""
    status: str = "pending"  # pending | accepted | rejected | modified
    language: str = "plaintext"
    change_type: str = "modify"  # create | modify | delete


@dataclass
class ComposerSession:
    """Tracks a single Composer editing session."""

    session_id: str
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"  # active | completed | cancelled | error
    files: dict[str, SessionFile] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def add_file(
        self,
        file_path: str,
        original_content: str = "",
        modified_content: str = "",
        language: str = "plaintext",
        change_type: str = "modify",
    ) -> SessionFile:
        """Add or update a file in the session."""
        sf = SessionFile(
            file_path=file_path,
            original_content=original_content,
            modified_content=modified_content,
            language=language,
            change_type=change_type,
            status="pending",
        )
        self.files[file_path] = sf
        self.updated_at = datetime.now().isoformat()
        return sf

    def remove_file(self, file_path: str) -> bool:
        """Remove a file from the session. Returns True if removed."""
        if file_path in self.files:
            del self.files[file_path]
            self.updated_at = datetime.now().isoformat()
            return True
        return False

    def update_file_content(self, file_path: str, modified_content: str) -> bool:
        """Update the modified content of a tracked file."""
        if file_path not in self.files:
            return False
        self.files[file_path].modified_content = modified_content
        self.files[file_path].status = "modified"
        self.updated_at = datetime.now().isoformat()
        return True

    def accept_file(self, file_path: str) -> bool:
        """Mark a file change as accepted."""
        if file_path not in self.files:
            return False
        self.files[file_path].status = "accepted"
        self.updated_at = datetime.now().isoformat()
        return True

    def reject_file(self, file_path: str) -> bool:
        """Mark a file change as rejected."""
        if file_path not in self.files:
            return False
        self.files[file_path].status = "rejected"
        self.updated_at = datetime.now().isoformat()
        return True

    def pending_count(self) -> int:
        """Number of files with pending status."""
        return sum(1 for f in self.files.values() if f.status == "pending")

    def accepted_count(self) -> int:
        """Number of files with accepted status."""
        return sum(1 for f in self.files.values() if f.status == "accepted")

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to a JSON-compatible dict."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "files": {k: asdict(v) for k, v in self.files.items()},
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComposerSession:
        """Deserialize a session from a dict."""
        files = {}
        for k, v in data.get("files", {}).items():
            files[k] = SessionFile(**v)
        return cls(
            session_id=data["session_id"],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            status=data.get("status", "active"),
            files=files,
            metadata=data.get("metadata", {}),
        )

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary of the session."""
        return {
            "session_id": self.session_id,
            "status": self.status,
            "file_count": len(self.files),
            "pending": self.pending_count(),
            "accepted": self.accepted_count(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SessionManager:
    """Manages multiple Composer sessions with persistence."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._sessions: dict[str, ComposerSession] = {}
        self._storage_dir: Path | None = (
            Path(storage_dir) if storage_dir else None
        )

    # ── CRUD ─────────────────────────────────────────────────────────

    def create_session(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ComposerSession:
        """Create a new Composer session."""
        sid = session_id or f"composer-{uuid.uuid4().hex[:12]}"
        session = ComposerSession(
            session_id=sid,
            metadata=metadata or {},
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> ComposerSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        status: str | None = None,
    ) -> list[ComposerSession]:
        """List all sessions, optionally filtered by status."""
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s.status == status]
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from memory and optionally from disk."""
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        # Also remove from disk if persisted
        if self._storage_dir:
            path = self._storage_dir / f"{session_id}.json"
            if path.exists():
                path.unlink()
        return True

    def complete_session(self, session_id: str) -> bool:
        """Mark a session as completed."""
        session = self.get_session(session_id)
        if not session:
            return False
        session.status = "completed"
        session.updated_at = datetime.now().isoformat()
        return True

    def cancel_session(self, session_id: str) -> bool:
        """Cancel an active session."""
        session = self.get_session(session_id)
        if not session:
            return False
        session.status = "cancelled"
        session.updated_at = datetime.now().isoformat()
        return True

    # ── Persistence ──────────────────────────────────────────────────

    def save_session(self, session_id: str) -> bool:
        """Persist a single session to disk."""
        session = self.get_session(session_id)
        if not session or not self._storage_dir:
            return False
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._storage_dir / f"{session_id}.json"
        path.write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True

    def load_session(self, session_id: str) -> ComposerSession | None:
        """Load a single session from disk."""
        if not self._storage_dir:
            return None
        path = self._storage_dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        session = ComposerSession.from_dict(data)
        self._sessions[session_id] = session
        return session

    def save_all(self) -> int:
        """Persist all active sessions to disk. Returns count saved."""
        count = 0
        if not self._storage_dir:
            return count
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        for sid, session in self._sessions.items():
            path = self._storage_dir / f"{sid}.json"
            path.write_text(
                json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            count += 1
        return count

    def load_all(self) -> int:
        """Load all sessions from disk into memory. Returns count loaded."""
        if not self._storage_dir or not self._storage_dir.exists():
            return 0
        count = 0
        for path in self._storage_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                session = ComposerSession.from_dict(data)
                self._sessions[session.session_id] = session
                count += 1
            except (json.JSONDecodeError, KeyError):
                continue
        return count

    # ── File management on sessions ──────────────────────────────────

    def add_file_to_session(
        self,
        session_id: str,
        file_path: str,
        original_content: str = "",
        modified_content: str = "",
        language: str = "plaintext",
        change_type: str = "modify",
    ) -> SessionFile | None:
        """Add a file to a session."""
        session = self.get_session(session_id)
        if not session:
            return None
        return session.add_file(
            file_path=file_path,
            original_content=original_content,
            modified_content=modified_content,
            language=language,
            change_type=change_type,
        )

    def remove_file_from_session(self, session_id: str, file_path: str) -> bool:
        """Remove a file from a session."""
        session = self.get_session(session_id)
        if not session:
            return False
        return session.remove_file(file_path)
