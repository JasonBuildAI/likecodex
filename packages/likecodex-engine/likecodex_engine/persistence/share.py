"""Session sharing service for LikeCodex engine.

Provides share-link generation, resolution, and revocation
backed by a separate SQLite table.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from likecodex_engine.errors import ValidationError


@dataclass
class SharedSession:
    """Represents a shared session link."""

    token: str
    session_id: str
    created_at: str
    expires_at: str
    password_hash: str | None
    revoked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionShareService:
    """Manages share-link lifecycle for agent sessions.

    Each share is identified by a unique token and optionally
    protected by a password.  Expired or revoked links are
    rejected at resolution time.
    """

    def __init__(self, db_path: str | Path = ".likecodex/sessions.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Schema ──────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shared_sessions (
                    token TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    password_hash TEXT,
                    revoked INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_shared_sessions_session
                ON shared_sessions (session_id)
                """
            )

    # ── Public API ──────────────────────────────────────────────────────

    def create_share_link(
        self,
        session_id: str,
        expiry_hours: int = 24,
        password: str | None = None,
    ) -> str:
        """Create a share link for *session_id*.

        Returns the unique token that can be used to resolve the share.
        """
        if expiry_hours < 1:
            raise ValidationError("expiry_hours must be >= 1", field="expiry_hours")
        if expiry_hours > 720:  # 30 days max
            raise ValidationError("expiry_hours must be <= 720", field="expiry_hours")

        token = self._generate_token()
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=expiry_hours)
        password_hash = self._hash_password(password) if password else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO shared_sessions
                    (token, session_id, created_at, expires_at, password_hash, metadata)
                VALUES (?, ?, ?, ?, ?, '{}')
                """,
                (token, session_id, now.isoformat(), expires_at.isoformat(), password_hash),
            )
        return token

    def resolve_share_link(
        self,
        token: str,
        password: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve a share link and return the associated session data.

        Returns ``None`` when the token is unknown, expired, or revoked.
        Raises :class:`ValidationError` when the password is wrong.
        """
        share = self._lookup(token)
        if share is None:
            return None

        if share.revoked:
            return None

        expires = datetime.fromisoformat(share.expires_at)
        if expires < datetime.now(UTC):
            return None

        if share.password_hash:
            if not password:
                raise ValidationError("This share is password-protected", field="password")
            if self._hash_password(password) != share.password_hash:
                raise ValidationError("Incorrect password", field="password")

        return {
            "token": share.token,
            "session_id": share.session_id,
            "created_at": share.created_at,
            "expires_at": share.expires_at,
            "metadata": share.metadata,
        }

    def revoke_share_link(self, token: str) -> bool:
        """Revoke a share link so it can no longer be resolved.

        Returns ``True`` if the token existed and was revoked.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE shared_sessions SET revoked = 1 WHERE token = ? AND revoked = 0",
                (token,),
            )
            return cursor.rowcount > 0

    def list_shared_sessions(
        self,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all active (non-revoked, non-expired) share links.

        If *session_id* is provided only shares for that session are returned.
        """
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT token, session_id, created_at, expires_at, metadata
                    FROM shared_sessions
                    WHERE session_id = ? AND revoked = 0 AND expires_at > ?
                    ORDER BY created_at DESC
                    """,
                    (session_id, now),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT token, session_id, created_at, expires_at, metadata
                    FROM shared_sessions
                    WHERE revoked = 0 AND expires_at > ?
                    ORDER BY created_at DESC
                    """,
                    (now,),
                ).fetchall()

        return [
            {
                "token": row[0],
                "session_id": row[1],
                "created_at": row[2],
                "expires_at": row[3],
                "metadata": json.loads(row[4] or "{}"),
            }
            for row in rows
        ]

    # ── Internals ───────────────────────────────────────────────────────

    @staticmethod
    def _generate_token() -> str:
        """Generate a cryptographically secure URL-safe token."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_password(password: str) -> str:
        """Return a SHA-256 hex digest of the password.

        NOTE: This is a simplified approach.  Production systems should
        use a proper key-derivation function (e.g. bcrypt / argon2).
        """
        return hashlib.sha256(password.encode()).hexdigest()

    def _lookup(self, token: str) -> SharedSession | None:
        """Return the raw ``SharedSession`` row or ``None``."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT token, session_id, created_at, expires_at,
                       password_hash, revoked, metadata
                FROM shared_sessions WHERE token = ?
                """,
                (token,),
            ).fetchone()
        if row is None:
            return None
        return SharedSession(
            token=row[0],
            session_id=row[1],
            created_at=row[2],
            expires_at=row[3],
            password_hash=row[4],
            revoked=bool(row[5]),
            metadata=json.loads(row[6] or "{}"),
        )

    def close(self) -> None:
        """Release any resources held by the service."""
        pass
