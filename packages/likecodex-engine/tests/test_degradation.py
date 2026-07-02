"""Tests for DegradationManager 5-level degradation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from likecodex_engine.agent.degradation import (
    DegradationEvent,
    DegradationLevel,
    DegradationManager,
    DegradationTrigger,
)


class TestDegradationLevel:
    """Tests for the DegradationLevel enum."""

    def test_values(self) -> None:
        assert DegradationLevel.NORMAL.value == 0
        assert DegradationLevel.RESTRICT_WRITE.value == 1
        assert DegradationLevel.READ_ONLY.value == 2
        assert DegradationLevel.ASK_ONLY.value == 3
        assert DegradationLevel.PLAIN_TEXT.value == 4

    def test_ordering(self) -> None:
        assert DegradationLevel.NORMAL < DegradationLevel.RESTRICT_WRITE
        assert DegradationLevel.PLAIN_TEXT > DegradationLevel.ASK_ONLY


class TestDegradationManagerInit:
    """Tests for DegradationManager initialization."""

    def test_default_level_normal(self) -> None:
        mgr = DegradationManager()
        assert mgr.current_level == DegradationLevel.NORMAL

    def test_custom_initial_level(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.READ_ONLY)
        assert mgr.current_level == DegradationLevel.READ_ONLY

    def test_custom_triggers(self) -> None:
        triggers = [DegradationTrigger(name="custom", threshold=2)]
        mgr = DegradationManager(triggers=triggers)
        assert "custom" in mgr._triggers

    def test_description_mapping(self) -> None:
        mgr = DegradationManager()
        assert "Full capabilities" in mgr.description


class TestDegradationEscalate:
    """Tests for degradation escalation."""

    def test_escalate_normal_to_restrict_write(self) -> None:
        mgr = DegradationManager()
        event = mgr.escalate()
        assert event is not None
        assert mgr.current_level == DegradationLevel.RESTRICT_WRITE
        assert event.previous_level == DegradationLevel.NORMAL
        assert event.level == DegradationLevel.RESTRICT_WRITE

    def test_escalate_max_level(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.PLAIN_TEXT)
        event = mgr.escalate()
        assert event is None  # Already at max

    def test_escalate_through_all_levels(self) -> None:
        mgr = DegradationManager()
        levels = []
        for _ in range(5):
            event = mgr.escalate()
            if event:
                levels.append(mgr.current_level)
        assert len(levels) == 5
        assert levels[-1] == DegradationLevel.PLAIN_TEXT

    def test_escalate_with_trigger_threshold_not_met(self) -> None:
        mgr = DegradationManager()
        trigger = DegradationTrigger(name="test", threshold=3)
        mgr._triggers["test"] = trigger

        # First call
        event = mgr.escalate("test")
        assert event is None  # threshold not met (1 < 3)

    def test_escalate_with_trigger_threshold_met(self) -> None:
        mgr = DegradationManager()
        trigger = DegradationTrigger(name="test", threshold=2)
        mgr._triggers["test"] = trigger

        mgr.escalate("test")  # count=1, not escalated
        event = mgr.escalate("test")  # count=2 >= 2, escalated
        assert event is not None
        assert mgr.current_level == DegradationLevel.RESTRICT_WRITE

    def test_escalate_calls_callback(self) -> None:
        callback = MagicMock()
        mgr = DegradationManager(on_escalate=callback)
        mgr.escalate()
        callback.assert_called_once()
        assert isinstance(callback.call_args[0][0], DegradationEvent)

    def test_escalate_model_switcher(self) -> None:
        switcher = MagicMock(return_value="cheap-model")
        mgr = DegradationManager(
            initial_level=DegradationLevel.NORMAL,
            model_switcher=switcher,
        )
        # First escalation to RESTRICT_WRITE should trigger model switch
        mgr.escalate()
        assert mgr.switched_model == "cheap-model"
        switcher.assert_called_once()

    def test_escalate_model_switcher_before_threshold(self) -> None:
        switcher = MagicMock(return_value="cheap-model")
        mgr = DegradationManager(model_switcher=switcher)
        # Model switch only happens at RESTRICT_WRITE or above
        # So at NORMAL, no switch yet
        # But escalate() goes straight to RESTRICT_WRITE which is >= RESTRICT_WRITE
        mgr.escalate()  # goes to level 1 (RESTRICT_WRITE)
        assert mgr.switched_model is not None

    def test_level_name_property(self) -> None:
        mgr = DegradationManager()
        assert mgr.level_name == "NORMAL"
        mgr.escalate()
        assert mgr.level_name == "RESTRICT_WRITE"


class TestDegradationRecover:
    """Tests for degradation recovery."""

    def test_recover_from_restrict_write(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.RESTRICT_WRITE)
        event = mgr.recover()
        assert event is not None
        assert mgr.current_level == DegradationLevel.NORMAL

    def test_recover_from_normal_noop(self) -> None:
        mgr = DegradationManager()
        event = mgr.recover()
        assert event is None

    def test_recover_cooldown(self) -> None:
        mgr = DegradationManager(
            initial_level=DegradationLevel.RESTRICT_WRITE,
            recovery_cooldown=999999.0,  # Very long cooldown
        )
        event = mgr.recover()
        assert event is not None  # First recovery should work
        event = mgr.recover()
        assert event is None  # Cooldown active

    def test_recover_max_attempts(self) -> None:
        import time as time_module

        mgr = DegradationManager(
            initial_level=DegradationLevel.RESTRICT_WRITE,
            recovery_cooldown=0.001,
            max_recovery_attempts=2,
        )
        # First recovery
        assert mgr.recover() is not None
        assert mgr.current_level == DegradationLevel.NORMAL

        # Escalate back
        mgr.escalate()
        assert mgr.current_level == DegradationLevel.RESTRICT_WRITE

        # Second recovery
        time_module.sleep(0.01)
        assert mgr.recover() is not None
        assert mgr.current_level == DegradationLevel.NORMAL

        # Escalate back
        mgr.escalate()
        assert mgr.current_level == DegradationLevel.RESTRICT_WRITE

        # Third recovery should be blocked (max_attempts=2)
        time_module.sleep(0.01)
        assert mgr.recover() is None

    def test_recover_calls_callback(self) -> None:
        callback = MagicMock()
        mgr = DegradationManager(
            initial_level=DegradationLevel.RESTRICT_WRITE,
            on_recover=callback,
        )
        mgr.recover()
        callback.assert_called_once()

    def test_recover_clears_switched_model(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.RESTRICT_WRITE)
        mgr._switched_model = "previous-model"
        mgr.recover()
        assert mgr.switched_model is None


class TestDegradationReset:
    """Tests for full reset."""

    def test_reset_to_normal(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.PLAIN_TEXT)
        event = mgr.reset()
        assert mgr.current_level == DegradationLevel.NORMAL
        assert event.previous_level == DegradationLevel.PLAIN_TEXT

    def test_reset_clears_counts(self) -> None:
        mgr = DegradationManager()
        mgr._trigger_counts = {"test": 5}
        mgr._recovery_attempts = 3
        mgr._switched_model = "some-model"
        mgr.reset()
        assert mgr._trigger_counts == {}
        assert mgr._recovery_attempts == 0
        assert mgr._switched_model is None

    def test_reset_creates_history_entry(self) -> None:
        mgr = DegradationManager()
        mgr.reset()
        assert len(mgr.history) == 1
        assert mgr.history[0].trigger == "reset"


class TestDegradationToolFilter:
    """Tests for tool filtering based on degradation level."""

    def test_normal_all_tools_allowed(self) -> None:
        mgr = DegradationManager()
        filters = mgr.get_tool_filter()
        assert filters["write"] is True
        assert filters["read"] is True
        assert filters["command"] is True
        assert filters["ask"] is True
        assert filters["all"] is True

    def test_restrict_write_blocks_write(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.RESTRICT_WRITE)
        filters = mgr.get_tool_filter()
        assert filters["write"] is False
        assert filters["command"] is True
        assert filters["read"] is True

    def test_read_only_blocks_write_and_command(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.READ_ONLY)
        filters = mgr.get_tool_filter()
        assert filters["write"] is False
        assert filters["command"] is False
        assert filters["read"] is True

    def test_ask_only_blocks_everything_except_ask(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.ASK_ONLY)
        filters = mgr.get_tool_filter()
        assert filters["write"] is False
        assert filters["command"] is False
        assert filters["read"] is False
        assert filters["ask"] is True

    def test_plain_text_blocks_all(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.PLAIN_TEXT)
        filters = mgr.get_tool_filter()
        assert filters["all"] is False

    def test_is_tool_allowed(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.RESTRICT_WRITE)
        assert mgr.is_tool_allowed("read_file", read_only=True) is True
        assert mgr.is_tool_allowed("write_file", read_only=False) is False
        assert mgr.is_tool_allowed("run_command", read_only=False) is True

    def test_is_tool_allowed_ask_only(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.ASK_ONLY)
        assert mgr.is_tool_allowed("ask") is True
        assert mgr.is_tool_allowed("read_file", read_only=True) is False

    def test_is_tool_allowed_plain_text(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.PLAIN_TEXT)
        assert mgr.is_tool_allowed("ask") is False
        assert mgr.is_tool_allowed("anything") is False


class TestDegradationHistory:
    """Tests for degradation event history."""

    def test_history_tracks_events(self) -> None:
        mgr = DegradationManager()
        mgr.escalate("trigger1")
        assert len(mgr.history) == 1
        assert mgr.history[0].trigger == "trigger1"

    def test_history_multiple_events(self) -> None:
        mgr = DegradationManager(initial_level=DegradationLevel.RESTRICT_WRITE)
        mgr.recover()
        mgr.escalate("test")
        mgr.reset()
        assert len(mgr.history) == 3


class TestDegradationSerialize:
    """Tests for serialization."""

    def test_to_dict(self) -> None:
        mgr = DegradationManager()
        data = mgr.to_dict()
        assert data["current_level"] == 0
        assert data["level_name"] == "NORMAL"
        assert data["history_count"] == 0
