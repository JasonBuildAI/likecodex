"""LLM streaming errors."""


class StreamInterruptedError(Exception):
    """Raised when a provider stream ends before completion."""
