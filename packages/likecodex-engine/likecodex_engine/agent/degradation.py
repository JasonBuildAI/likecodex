"""Dynamic degradation manager for graceful system degradation.

Provides 5 levels of degradation (Level 0 = normal, Level 4 = pure text),
with automatic escalation triggers and recovery capabilities.

The degradation manager integrates with:
- Model switching (cheaper/faster models under pressure)
- Tool restrictions (write tools, then all tools)
- Context compaction
- Sandbox fallback limits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class DegradationLevel(IntEnum):
    """Five levels of system degradation.

    Each level progressively restricts functionality to maintain
    basic operation under adverse conditions.
    """

    NORMAL = 0  # Full capabilities
    RESTRICT_WRITE = 1  # Block write/edit tools, read-only + commands
    READ_ONLY = 2  # Only read/search tools, no commands
    ASK_ONLY = 3  # Only ask tool, no automated operations
    PLAIN_TEXT = 4  # No tools at all, pure text generation only


# Mapping of degradation levels to human-readable descriptions
_DEGRADATION_DESCRIPTIONS: dict[DegradationLevel, str] = {
    DegradationLevel.NORMAL: "Full capabilities — all tools available.",
    DegradationLevel.RESTRICT_WRITE: "Write operations blocked. Read-only and command tools only.",
    DegradationLevel.READ_ONLY: "Read/search only. No write or command execution.",
    DegradationLevel.ASK_ONLY: "Ask tool only. No automated operations.",
    DegradationLevel.PLAIN_TEXT: "Pure text generation. All tools disabled.",
}


@dataclass
class DegradationTrigger:
    """Configuration for an automatic degradation trigger.

    Attributes:
        name: Human-readable trigger name.
        threshold: Number of occurrences before escalation.
        description: Why this trigger exists.
    """

    name: str
    threshold: int = 3
    description: str = ""


# Default triggers for automatic degradation escalation
_DEFAULT_TRIGGERS: list[DegradationTrigger] = [
    DegradationTrigger(
        name="stream_recovery_exhausted",
        threshold=1,
        description="Stream recovery exhausted multiple times.",
    ),
    DegradationTrigger(
        name="sandbox_fallback_exceeded",
        threshold=3,
        description="Sandbox unavailable, repeated fallback to local.",
    ),
    DegradationTrigger(
        name="empty_final_blocks",
        threshold=3,
        description="Model returned empty responses consecutively.",
    ),
    DegradationTrigger(
        name="tool_failure_storm",
        threshold=5,
        description="Repeated tool failures across multiple turns.",
    ),
    DegradationTrigger(
        name="api_timeout",
        threshold=2,
        description="API timeout or rate-limit exceeded.",
    ),
]


@dataclass
class DegradationEvent:
    """Event emitted on degradation level change."""

    level: DegradationLevel
    previous_level: DegradationLevel
    trigger: str = ""
    message: str = ""
    action_taken: str = ""


class DegradationManager:
    """Manages system degradation levels and automatic escalation/recovery.

    Features:
    - 5 progressive degradation levels
    - Automatic escalation on trigger thresholds
    - Recovery with cooldown to prevent thrashing
    - Model switching integration
    - Tool restriction enforcement
    - Events for observability

    Usage::

        mgr = DegradationManager()
        mgr.escalate("sandbox_fallback_exceeded")
        if mgr.current_level >= DegradationLevel.RESTRICT_WRITE:
            # filter tools ...
        mgr.recover()  # try to recover one level
    """

    def __init__(
        self,
        initial_level: DegradationLevel = DegradationLevel.NORMAL,
        triggers: list[DegradationTrigger] | None = None,
        on_escalate: Callable[[DegradationEvent], None] | None = None,
        on_recover: Callable[[DegradationEvent], None] | None = None,
        recovery_cooldown: float = 30.0,
        max_recovery_attempts: int = 3,
        model_switcher: Callable[[DegradationLevel], str | None] | None = None,
    ) -> None:
        self._current_level = initial_level
        self._triggers = {t.name: t for t in (triggers or _DEFAULT_TRIGGERS)}
        self._trigger_counts: dict[str, int] = {}
        self._on_escalate = on_escalate
        self._on_recover = on_recover
        self._recovery_cooldown = recovery_cooldown
        self._max_recovery_attempts = max_recovery_attempts
        self._recovery_attempts = 0
        self._last_recovery_time: float = 0.0
        self._model_switcher = model_switcher
        self._history: list[DegradationEvent] = []
        self._switched_model: str | None = None

    @property
    def current_level(self) -> DegradationLevel:
        return self._current_level

    @property
    def level_name(self) -> str:
        return self._current_level.name

    @property
    def description(self) -> str:
        return _DEGRADATION_DESCRIPTIONS.get(self._current_level, "Unknown state.")

    @property
    def switched_model(self) -> str | None:
        return self._switched_model

    @property
    def history(self) -> list[DegradationEvent]:
        return list(self._history)

    def escalate(self, trigger: str = "") -> DegradationEvent | None:
        """Escalate one degradation level.

        Args:
            trigger: Optional trigger name for tracking and observability.

        Returns:
            DegradationEvent if level changed, None if already at max level.
        """
        if self._current_level >= DegradationLevel.PLAIN_TEXT:
            logger.debug("Already at max degradation level (%s)", self._current_level.name)
            return None

        # Check trigger threshold if specified
        if trigger:
            self._trigger_counts[trigger] = self._trigger_counts.get(trigger, 0) + 1
            trigger_def = self._triggers.get(trigger)
            if trigger_def and self._trigger_counts[trigger] < trigger_def.threshold:
                logger.debug(
                    "Trigger '%s' count %d/%d, not escalating yet",
                    trigger,
                    self._trigger_counts[trigger],
                    trigger_def.threshold,
                )
                return None

        prev = self._current_level
        self._current_level = DegradationLevel(self._current_level + 1)
        action = self._get_escalation_action()

        # Attempt model switch if configured
        if self._model_switcher and self._current_level >= DegradationLevel.RESTRICT_WRITE:
            try:
                model = self._model_switcher(self._current_level)
                if model:
                    self._switched_model = model
                    action += f" Switched model to {model}."
            except Exception as exc:
                logger.warning("Model switcher failed: %s", exc)

        event = DegradationEvent(
            level=self._current_level,
            previous_level=prev,
            trigger=trigger,
            message=f"Degraded from {prev.name} to {self._current_level.name}: {action}",
            action_taken=action,
        )
        self._history.append(event)
        logger.warning("Degradation escalated: %s -> %s (%s)", prev.name, self._current_level.name, trigger)

        if self._on_escalate:
            try:
                self._on_escalate(event)
            except Exception as exc:
                logger.error("on_escalate callback failed: %s", exc)

        return event

    def recover(self) -> DegradationEvent | None:
        """Attempt to recover one degradation level.

        Recovery is subject to cooldown and max attempt limits
        to prevent thrashing between levels.

        Returns:
            DegradationEvent if recovery happened, None otherwise.
        """
        if self._current_level <= DegradationLevel.NORMAL:
            logger.debug("Already at normal level, no recovery needed.")
            return None

        import time

        now = time.time()
        if now - self._last_recovery_time < self._recovery_cooldown:
            logger.debug("Recovery cooldown active, skipping.")
            return None

        if self._recovery_attempts >= self._max_recovery_attempts:
            logger.debug("Max recovery attempts (%d) reached.", self._max_recovery_attempts)
            return None

        prev = self._current_level
        self._current_level = DegradationLevel(self._current_level - 1)
        self._recovery_attempts += 1
        self._last_recovery_time = now
        self._switched_model = None

        event = DegradationEvent(
            level=self._current_level,
            previous_level=prev,
            trigger="recovery",
            message=f"Recovered from {prev.name} to {self._current_level.name}.",
            action_taken=f"recovered_to_{self._current_level.name}",
        )
        self._history.append(event)
        logger.info("Degradation recovered: %s -> %s", prev.name, self._current_level.name)

        if self._on_recover:
            try:
                self._on_recover(event)
            except Exception as exc:
                logger.error("on_recover callback failed: %s", exc)

        return event

    def reset(self) -> DegradationEvent:
        """Fully reset to normal level."""
        prev = self._current_level
        self._current_level = DegradationLevel.NORMAL
        self._trigger_counts.clear()
        self._recovery_attempts = 0
        self._switched_model = None

        event = DegradationEvent(
            level=DegradationLevel.NORMAL,
            previous_level=prev,
            trigger="reset",
            message=f"Reset from {prev.name} to NORMAL.",
            action_taken="reset_to_normal",
        )
        self._history.append(event)
        logger.info("Degradation reset: %s -> NORMAL", prev.name)
        return event

    def get_tool_filter(self) -> dict[str, bool]:
        """Return a filter dict indicating which tool categories are allowed.

        Returns a dict with keys like 'write', 'read', 'command', 'ask', 'all'
        mapped to booleans indicating whether that category is allowed.
        """
        level = self._current_level
        return {
            "write": level < DegradationLevel.RESTRICT_WRITE,
            "command": level < DegradationLevel.READ_ONLY,
            "read": level < DegradationLevel.ASK_ONLY,
            "ask": level < DegradationLevel.PLAIN_TEXT,
            "all": level < DegradationLevel.PLAIN_TEXT,
        }

    def is_tool_allowed(self, tool_name: str, read_only: bool = False) -> bool:
        """Check if a tool is allowed at the current degradation level.

        Args:
            tool_name: Name of the tool to check.
            read_only: Whether this is a read-only tool.
        """
        level = self._current_level
        if level >= DegradationLevel.PLAIN_TEXT:
            return False
        if level >= DegradationLevel.ASK_ONLY:
            return tool_name == "ask"
        if level >= DegradationLevel.READ_ONLY:
            return read_only
        if level >= DegradationLevel.RESTRICT_WRITE:
            return read_only or tool_name in ("run_command", "ask")
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for logging/observability."""
        return {
            "current_level": self._current_level.value,
            "level_name": self._current_level.name,
            "trigger_counts": dict(self._trigger_counts),
            "recovery_attempts": self._recovery_attempts,
            "switched_model": self._switched_model,
            "history_count": len(self._history),
        }

    @staticmethod
    def _get_escalation_action() -> str:
        return (
            "Write tools blocked, model may be switched."
            # Detailed action depends on the level, handled at the call site.
        )
