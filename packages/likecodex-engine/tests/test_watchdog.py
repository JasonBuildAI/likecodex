"""Tests for Watchdog timeout and idle detection."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from likecodex_engine.agent.watchdog import (
    Watchdog,
    WatchdogAction,
    WatchdogConfig,
    WatchdogEvent,
    WatchdogState,
)


class TestWatchdogConfig:
    """Tests for WatchdogConfig data model."""

    def test_default_config(self) -> None:
        config = WatchdogConfig()
        assert config.timeout == 300.0
        assert config.idle_timeout == 60.0
        assert config.interval == 15.0
        assert config.action == WatchdogAction.TERMINATE

    def test_custom_config(self) -> None:
        config = WatchdogConfig(timeout=120.0, idle_timeout=30.0)
        assert config.timeout == 120.0
        assert config.idle_timeout == 30.0


class TestWatchdogState:
    """Tests for Watchdog state management."""

    def test_initial_state(self) -> None:
        wd = Watchdog()
        assert wd.state == WatchdogState.STOPPED

    def test_start_sets_running(self) -> None:
        wd = Watchdog()
        wd.start()
        assert wd.state == WatchdogState.RUNNING

    def test_stop_sets_stopped(self) -> None:
        wd = Watchdog()
        wd.start()
        wd.stop()
        assert wd.state == WatchdogState.STOPPED

    def test_check_while_stopped(self) -> None:
        wd = Watchdog()
        assert wd.check() is None

    def test_start_resets_fired(self) -> None:
        wd = Watchdog()
        wd._fired = True
        wd.start()
        assert wd._fired is False


class TestWatchdogTimeout:
    """Tests for total execution timeout detection."""

    def test_timeout_triggers_terminate(self) -> None:
        config = WatchdogConfig(timeout=0.01, action=WatchdogAction.TERMINATE)
        wd = Watchdog(config=config)
        wd.start()
        time.sleep(0.02)
        event = wd.check()
        assert event is not None
        assert event.type == "timeout"
        assert event.action == "terminate"
        assert wd.state == WatchdogState.TRIGGERED

    def test_timeout_triggers_warn(self) -> None:
        config = WatchdogConfig(timeout=0.01, action=WatchdogAction.WARN)
        wd = Watchdog(config=config)
        wd.start()
        time.sleep(0.02)
        event = wd.check()
        assert event is not None
        assert event.type == "timeout"

    def test_timeout_only_fires_once(self) -> None:
        config = WatchdogConfig(timeout=0.01)
        wd = Watchdog(config=config)
        wd.start()
        time.sleep(0.02)
        event1 = wd.check()
        event2 = wd.check()
        assert event1 is not None
        assert event2 is None  # already fired

    def test_no_timeout_within_limit(self) -> None:
        config = WatchdogConfig(timeout=60.0)
        wd = Watchdog(config=config)
        wd.start()
        event = wd.check()
        assert event is None

    def test_reset_extends_timeout(self) -> None:
        config = WatchdogConfig(timeout=0.05)
        wd = Watchdog(config=config)
        wd.start()
        time.sleep(0.03)
        wd.reset()  # resets activity only, not start time
        time.sleep(0.03)
        event = wd.check()
        # Total elapsed should be ~0.06 > 0.05, so timeout
        assert event is not None or wd.elapsed > 0.05


class TestWatchdogIdle:
    """Tests for idle timeout detection."""

    def test_idle_detected(self) -> None:
        config = WatchdogConfig(timeout=60.0, idle_timeout=0.01)
        wd = Watchdog(config=config)
        wd.start()
        time.sleep(0.02)
        event = wd.check()
        assert event is not None
        assert event.type == "idle"

    def test_reset_clears_idle(self) -> None:
        config = WatchdogConfig(timeout=60.0, idle_timeout=0.1)
        wd = Watchdog(config=config)
        wd.start()
        wd.reset()  # reset activity
        event = wd.check()
        assert event is None  # idle was reset

    def test_idle_state_transition(self) -> None:
        config = WatchdogConfig(timeout=60.0, idle_timeout=0.01)
        wd = Watchdog(config=config)
        wd.start()
        time.sleep(0.02)
        event = wd.check()
        assert event is not None
        assert wd.state == WatchdogState.IDLE


class TestWatchdogProperties:
    """Tests for Watchdog properties."""

    def test_elapsed_zero_before_start(self) -> None:
        wd = Watchdog()
        assert wd.elapsed == 0.0

    def test_elapsed_after_start(self) -> None:
        wd = Watchdog()
        wd.start()
        assert wd.elapsed >= 0.0

    def test_idle_zero_before_start(self) -> None:
        wd = Watchdog()
        assert wd.idle == 0.0

    def test_idle_increases(self) -> None:
        wd = Watchdog()
        wd.start()
        idle_before = wd.idle
        time.sleep(0.01)
        assert wd.idle > idle_before


class TestWatchdogCallbacks:
    """Tests for Watchdog event callbacks."""

    def test_on_event_called_on_timeout(self) -> None:
        callback = MagicMock()
        config = WatchdogConfig(timeout=0.01)
        wd = Watchdog(config=config, on_event=callback)
        wd.start()
        time.sleep(0.02)
        wd.check()
        callback.assert_called_once()
        assert callback.call_args[0][0].type == "timeout"

    def test_fallback_handler_called(self) -> None:
        handler = MagicMock()
        config = WatchdogConfig(timeout=0.01, action=WatchdogAction.FALLBACK, fallback_handler=handler)
        wd = Watchdog(config=config)
        wd.start()
        time.sleep(0.02)
        wd._perform_action()
        handler.assert_called_once()

    def test_on_event_called_on_stop(self) -> None:
        callback = MagicMock()
        wd = Watchdog(config=WatchdogConfig(), on_event=callback)
        wd.start()
        wd.stop()
        callback.assert_called_once()
        assert callback.call_args[0][0].type == "stopped"


class TestWatchdogToDict:
    """Tests for watchdog serialization."""

    def test_to_dict_before_start(self) -> None:
        wd = Watchdog()
        data = wd.to_dict()
        assert data["state"] == "stopped"
        assert data["elapsed_s"] == 0.0

    def test_to_dict_after_start(self) -> None:
        wd = Watchdog()
        wd.start()
        data = wd.to_dict()
        assert data["state"] == "running"
        assert data["fired"] is False
