"""SQLite-based session persistence for agent conversations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from likecodex_engine.llm.base import Message


@dataclass
class SessionEvent:
    event_type: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str | None = None


class SessionStore:
    """Stores and retrieves agent session history."""

    def __init__(self, db_path: str | Path = ".likecodex/sessions.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    content TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
                """
            )

    def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        metadata = metadata or {}
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT metadata FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if existing:
                merged = json.loads(existing[0] or "{}")
                merged.update(metadata)
                metadata = merged
            conn.execute(
                "INSERT OR REPLACE INTO sessions (id, metadata) VALUES (?, ?)",
                (session_id, json.dumps(metadata)),
            )

    def get_session_metadata(self, session_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT metadata FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return {}
        return json.loads(row[0] or "{}")

    def list_events(self, session_id: str) -> list[SessionEvent]:
        return self.get_events(session_id)

    def append_event(self, session_id: str, event: SessionEvent) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO events (session_id, event_type, content, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    event.event_type,
                    event.content,
                    json.dumps(event.metadata),
                ),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )

    def get_events(self, session_id: str, event_type: str | None = None) -> list[SessionEvent]:
        with sqlite3.connect(self.db_path) as conn:
            if event_type:
                rows = conn.execute(
                    """
                    SELECT event_type, content, metadata, created_at
                    FROM events
                    WHERE session_id = ? AND event_type = ?
                    ORDER BY id
                    """,
                    (session_id, event_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT event_type, content, metadata, created_at
                    FROM events
                    WHERE session_id = ?
                    ORDER BY id
                    """,
                    (session_id,),
                ).fetchall()
        return [
            SessionEvent(
                event_type=row[0],
                content=row[1],
                metadata=json.loads(row[2] or "{}"),
                timestamp=row[3],
            )
            for row in rows
        ]

    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, updated_at, metadata
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "metadata": json.loads(row[3] or "{}"),
            }
            for row in rows
        ]

    def rebuild_context(self, session_id: str) -> list[Message]:
        """Rebuild a message context from persisted assistant/user/tool events."""
        messages: list[Message] = []
        for event in self.get_events(session_id):
            if event.event_type == "user":
                messages.append(Message(role="user", content=event.content))
            elif event.event_type == "assistant":
                tool_calls = event.metadata.get("tool_calls")
                raw_tool_calls = event.metadata.get("raw_tool_calls")
                messages.append(
                    Message(
                        role="assistant",
                        content=event.content,
                        tool_calls=tool_calls,
                        raw_tool_calls=raw_tool_calls,
                    )
                )
            elif event.event_type == "tool_result":
                tool_call_id = event.metadata.get("tool_call_id")
                messages.append(Message(role="tool", content=event.content, tool_call_id=tool_call_id))
        return messages

    def restore_context_manager(self, session_id: str) -> ContextManager | None:
        """Rebuild a ContextManager with stable SYSTEM prefix from session events."""
        from likecodex_engine.context.manager import ContextManager

        restored = self.rebuild_context(session_id)
        if not restored:
            return None
        manager = ContextManager()
        manager._log = restored
        return manager
