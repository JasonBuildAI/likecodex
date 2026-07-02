"""Unified error types and handling for LikeCodex engine.

Provides a consistent error hierarchy used across the codebase.
All custom exceptions inherit from LikeCodexError.

Usage:
    raise ConfigError("Missing API key")
    raise EngineError("Engine not running", status_code=503)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "LikeCodexError",
    "ConfigError",
    "EngineError",
    "APIError",
    "ProviderError",
    "ToolError",
    "ValidationError",
    "PermissionError",
    "SessionError",
]


class LikeCodexError(Exception):
    """Base exception for all LikeCodex errors."""

    def __init__(self, message: str, *, status_code: int = 500, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to a JSON-serializable dict."""
        return {
            "error": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }


class ConfigError(LikeCodexError):
    """Configuration-related errors (missing fields, invalid values)."""

    def __init__(self, message: str, *, missing_fields: list[str] | None = None, **kwargs: Any) -> None:
        details = kwargs.pop("details", {})
        if missing_fields:
            details["missing_fields"] = missing_fields
        super().__init__(message, status_code=400, details=details, **kwargs)


class EngineError(LikeCodexError):
    """Engine runtime errors (server issues, startup failures)."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, status_code=500, **kwargs)


class APIError(LikeCodexError):
    """API-level errors (bad requests, routing issues)."""

    def __init__(self, message: str, *, status_code: int = 400, **kwargs: Any) -> None:
        super().__init__(message, status_code=status_code, **kwargs)


class ProviderError(LikeCodexError):
    """LLM provider errors (API failures, rate limits, auth issues)."""

    def __init__(self, message: str, *, provider: str | None = None, **kwargs: Any) -> None:
        details = kwargs.pop("details", {})
        if provider:
            details["provider"] = provider
        super().__init__(message, status_code=502, details=details, **kwargs)


class ToolError(LikeCodexError):
    """Tool execution errors."""

    def __init__(self, message: str, *, tool_name: str | None = None, **kwargs: Any) -> None:
        details = kwargs.pop("details", {})
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, status_code=500, details=details, **kwargs)


class ValidationError(LikeCodexError):
    """Input validation errors."""

    def __init__(self, message: str, *, field: str | None = None, **kwargs: Any) -> None:
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        super().__init__(message, status_code=422, details=details, **kwargs)


class PermissionError(LikeCodexError):
    """Permission/approval errors."""

    def __init__(self, message: str, *, required_mode: str | None = None, **kwargs: Any) -> None:
        details = kwargs.pop("details", {})
        if required_mode:
            details["required_mode"] = required_mode
        super().__init__(message, status_code=403, details=details, **kwargs)


class SessionError(LikeCodexError):
    """Session management errors."""

    def __init__(self, message: str, *, session_id: str | None = None, **kwargs: Any) -> None:
        details = kwargs.pop("details", {})
        if session_id:
            details["session_id"] = session_id
        super().__init__(message, status_code=404, details=details, **kwargs)
