"""Configurable watchdog timer for agent loop monitoring.

Provides timeout detection with configurable actions:
terminate, warn, or fallback to a safe mode.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class WatchdogAction(Enum):
    """Actions to take when watchdog timeout fires."""

    TERMINATE = "terminate"  # Forcefully stop the loop
    WARN = "warn"  # Only emit a warning, continue execution
    FALLBACK = "fallback"  # Switch to fallback/safe mode


@dataclass
class WatchdogConfig:
    """Configuration for the watchdog timer.

    Attributes:
        interval: How often (seconds) to check if the watchdog is alive.
        timeout: Maximum total execution time (seconds) before triggering.
        idle_timeout: Maximum idle time (seconds) with no activity.
        action: Action to take on timeout.
        warn_threshold: If action is WARN, threshold of remaining time to warn.
        fallback_handler: Optional callable for FALLBACK action.
    """

    interval: float = 15.0
    timeout: float = 300.0  # 5 minutes
    idle_timeout: float = 60.0  # 1 minute
    action: WatchdogAction = WatchdogAction.TERMINATE
    warn_threshold: float = 30.0
    fallback_handler: Callable[[], Any] | None = None


class WatchdogState(Enum):
    """Current state of the watchdog."""

    RUNNING = "running"
    IDLE = "idle"
    TRIGGERED = "triggered"
    STOPPED = "stopped"


@dataclass
class WatchdogEvent:
    """Event emitted by the watchdog."""

    type: str  # "timeout", "idle", "heartbeat", "stopped"
    message: str = ""
    elapsed: float = 0.0
    idle: float = 0.0
    action: str = ""


class Watchdog:
    """Configurable watchdog timer for monitoring agent loop health.

    Provides periodic checks with configurable timeout, idle detection,
    and actions on timeout (terminate / warn / fallback).

    Usage::

        watchdog = Watchdog(WatchdogConfig(timeout=120, action=WatchdogAction.WARN))
        watchdog.start()
        # ... do work ...
        watchdog.reset()
        # ... on each tick ...
        event = watchdog.check()
        if event:
            handle_event(event)
    """

    def __init__(
        self,
        config: WatchdogConfig | None = None,
        on_event: Callable[[WatchdogEvent], None] | None = None,
    ) -> None:
        self.config = config or WatchdogConfig()
        self.on_event = on_event
        self._start_time: float = 0.0
        self._last_activity: float = 0.0
        self._last_check: float = 0.0
        self._state = WatchdogState.STOPPED
        self._fired: bool = False
        self._timer_task: asyncio.Task[None] | None = None

    @property
    def elapsed(self) -> float:
        """Seconds since watchdog was started."""
        if not self._start_time:
            return 0.0
        return time.time() - self._start_time

    @property
    def idle(self) -> float:
        """Seconds since last activity reset."""
        if not self._last_activity:
            return 0.0
        return time.time() - self._last_activity

    @property
    def state(self) -> WatchdogState:
        return self._state

    def start(self) -> None:
        """Start the watchdog timer."""
        now = time.time()
        self._start_time = now
        self._last_activity = now
        self._last_check = now
        self._state = WatchdogState.RUNNING
        self._fired = False
        logger.debug("Watchdog started (timeout=%ss, idle=%ss)", self.config.timeout, self.config.idle_timeout)

    def reset(self) -> None:
        """Reset the activity timer (call after any meaningful progress)."""
        self._last_activity = time.time()
        self._fired = False
        if self._state == WatchdogState.RUNNING:
            self._state = WatchdogState.RUNNING
        logger.debug("Watchdog reset: activity timestamp updated")

    def check(self) -> WatchdogEvent | None:
        """Periodic health check. Returns a WatchdogEvent if action is needed.

        Should be called at each iteration of the agent loop.
        """
        if self._state == WatchdogState.STOPPED:
            return None

        now = time.time()
        self._last_check = now
        elapsed = now - self._start_time
        idle = now - self._last_activity

        # Check total timeout
        if elapsed >= self.config.timeout and not self._fired:
            self._fired = True
            self._state = WatchdogState.TRIGGERED
            event = WatchdogEvent(
                type="timeout",
                message=f"Total execution time {elapsed:.1f}s exceeded {self.config.timeout}s timeout.",
                elapsed=elapsed,
                idle=idle,
                action=self.config.action.value,
            )
            self._emit(event)
            self._perform_action()
            return event

        # Check idle timeout
        if idle >= self.config.idle_timeout:
            if self._state != WatchdogState.IDLE:
                self._state = WatchdogState.IDLE
                event = WatchdogEvent(
                    type="idle",
                    message=f"Idle for {idle:.1f}s (threshold: {self.config.idle_timeout}s).",
                    elapsed=elapsed,
                    idle=idle,
                    action="idle_warning",
                )
                self._emit(event)
                return event

        # Warn if approaching timeout
        remaining = self.config.timeout - elapsed
        if self.config.action == WatchdogAction.WARN and remaining <= self.config.warn_threshold:
            if not self._fired:
                self._fired = True
                event = WatchdogEvent(
                    type="heartbeat",
                    message=f"Approaching timeout: {remaining:.1f}s remaining.",
                    elapsed=elapsed,
                    idle=idle,
                    action="warn",
                )
                self._emit(event)
                return event

        return None

    def stop(self) -> None:
        """Stop the watchdog."""
        old_state = self._state
        self._state = WatchdogState.STOPPED
        self._cancel_timer()
        if old_state != WatchdogState.STOPPED:
            self._emit(
                WatchdogEvent(
                    type="stopped",
                    message="Watchdog stopped.",
                    elapsed=self.elapsed,
                    idle=self.idle,
                    action="stop",
                )
            )

    def _perform_action(self) -> None:
        """Execute the configured action on timeout."""
        action = self.config.action
        logger.warning("Watchdog performing action: %s", action.value)
        if action == WatchdogAction.FALLBACK and self.config.fallback_handler:
            try:
                self.config.fallback_handler()
            except Exception as exc:
                logger.error("Watchdog fallback handler failed: %s", exc)

    def _emit(self, event: WatchdogEvent) -> None:
        """Emit event to the registered callback."""
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as exc:
                logger.error("Watchdog on_event callback failed: %s", exc)

    def _cancel_timer(self) -> None:
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize watchdog state for logging/metrics."""
        return {
            "elapsed_s": round(self.elapsed, 1),
            "idle_s": round(self.idle, 1),
            "state": self._state.value,
            "timeout_s": self.config.timeout,
            "idle_timeout_s": self.config.idle_timeout,
            "action": self.config.action.value,
            "fired": self._fired,
        }
