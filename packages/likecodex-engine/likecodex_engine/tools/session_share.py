"""Session sharing and export/import tools."""

from __future__ import annotations

import json
import time
from typing import Any


class SessionShareTools:
    """Tools for sharing, exporting, and importing sessions."""

    @staticmethod
    def share_schema() -> dict[str, Any]:
        return {
            "description": "Share a session as a link, JSON, Markdown, or HTML export.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to share",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["link", "json", "markdown", "html"],
                        "default": "markdown",
                        "description": "Output format for the shared session",
                    },
                    "expiry": {
                        "type": "integer",
                        "default": 86400,
                        "description": "Expiry time in seconds (default 24h)",
                    },
                },
                "required": ["session_id"],
            },
        }

    @staticmethod
    def export_schema() -> dict[str, Any]:
        return {
            "description": "Export a session in the specified format (JSON / Markdown / HTML).",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to export",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "markdown", "html"],
                        "default": "json",
                    },
                },
                "required": ["session_id"],
            },
        }

    @staticmethod
    def import_schema() -> dict[str, Any]:
        return {
            "description": "Import a session from JSON serialized data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "JSON string containing session data",
                    },
                },
                "required": ["data"],
            },
        }

    async def share(
        self,
        session_id: str,
        format: str = "markdown",
        expiry: int = 86400,
    ) -> str:
        try:
            token = f"share_{int(time.time())}_{session_id[:8]}"
            if format == "link":
                return json.dumps({
                    "url": f"https://likecodex.app/share/{token}",
                    "token": token,
                    "expires_in": expiry,
                    "format": format,
                })
            content = self._render(session_id, format)
            return json.dumps({
                "token": token,
                "format": format,
                "content": content,
                "expires_in": expiry,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def export(self, session_id: str, format: str = "json") -> str:
        try:
            content = self._render(session_id, format)
            return json.dumps({
                "session_id": session_id,
                "format": format,
                "content": content,
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def import_(self, data: str) -> str:
        try:
            parsed = json.loads(data)
            return json.dumps({
                "status": "imported",
                "messages_count": len(parsed.get("messages", [])),
                "session_id": parsed.get("session_id", "imported"),
            })
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON data"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @staticmethod
    def _render(session_id: str, fmt: str) -> str:
        if fmt == "json":
            return json.dumps({"session_id": session_id, "exported_at": time.time()})
        if fmt == "markdown":
            return (
                f"# Session: {session_id}\n\n"
                f"- **Exported at**: {time.ctime()}\n"
                f"- **Messages**: (export placeholder)\n"
            )
        if fmt == "html":
            return (
                f"<html><body><h1>Session: {session_id}</h1>"
                f"<p>Exported at: {time.ctime()}</p></body></html>"
            )
        if fmt == "link":
            return f"https://likecodex.app/share/{session_id}"
        return ""
