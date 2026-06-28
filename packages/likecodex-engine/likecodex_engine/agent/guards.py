"""Loop/storm guards for repeated tool failures and write loops."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from likecodex_engine.context.utils import stable_json_dumps

STORM_BREAK_THRESHOLD = 3
REPEAT_SUCCESS_THRESHOLD = 3
LOOP_GUARD_PREFIX = "[loop guard]"
WRITE_LIKE_TOOLS = frozenset(
    {
        "write_file",
        "edit_file",
        "multi_edit",
        "move_file",
        "notebook_edit",
    }
)


@dataclass
class LoopGuard:
    """Tracks consecutive failures for the same tool invocation."""

    threshold: int = STORM_BREAK_THRESHOLD
    _failures: dict[str, int] = field(default_factory=dict)
    _last_error: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def _key(tool_name: str, arguments: dict[str, Any]) -> str:
        return f"{tool_name}:{stable_json_dumps(arguments)}"

    def record_failure(self, tool_name: str, arguments: dict[str, Any], error: str) -> bool:
        """Record a failure. Returns True if loop guard should fire."""
        key = self._key(tool_name, arguments)
        self._failures[key] = self._failures.get(key, 0) + 1
        self._last_error[key] = error
        return self._failures[key] >= self.threshold

    def record_success(self, tool_name: str, arguments: dict[str, Any]) -> None:
        key = self._key(tool_name, arguments)
        self._failures.pop(key, None)
        self._last_error.pop(key, None)

    def guard_message(self, tool_name: str, arguments: dict[str, Any], original_error: str) -> str:
        return (
            f"{LOOP_GUARD_PREFIX} Tool `{tool_name}` failed {self.threshold} times with the same arguments. "
            f"Stop retrying this approach and try a different strategy. Original error: {original_error}"
        )

    def is_error_result(self, result: str) -> bool:
        return self.error_from_result(result) is not None

    def extract_error(self, result: str) -> str:
        err = self.error_from_result(result)
        return err if err is not None else result[:500]

    def error_from_result(self, result: str) -> str | None:
        """Parse result once and return error message or None."""
        try:
            data = json.loads(result)
        except json.JSONDecodeError:
            return "error" if "error" in result.lower() else None
        if isinstance(data, dict):
            if data.get("error"):
                return str(data["error"])
            if data.get("exit_code") not in (None, 0) and "stdout" in data:
                return None
        return None


@dataclass
class ToolTurnOutcome:
    """One tool call's result within a model turn (for cross-turn storm detection)."""

    tool_call_id: str
    tool_name: str
    output: str
    error_msg: str = ""
    blocked: bool = False


def batch_storm_signature(outcomes: list[ToolTurnOutcome]) -> tuple[str, bool]:
    """Return a per-turn fixation signature when every call errored and none was blocked."""
    if not outcomes:
        return "", False
    parts: list[str] = []
    for outcome in outcomes:
        if not outcome.error_msg or outcome.blocked:
            return "", False
        parts.extend((outcome.tool_name, outcome.error_msg))
    return "\0".join(parts), True


@dataclass
class StormBreaker:
    """Detects repeated all-failing tool batches across turns (Reasonix applyStormBreaker)."""

    threshold: int = STORM_BREAK_THRESHOLD
    storm_sig: str = ""
    storm_count: int = 0

    def reset(self) -> None:
        self.storm_sig = ""
        self.storm_count = 0

    def apply_turn(self, outcomes: list[ToolTurnOutcome]) -> tuple[str, str, str] | None:
        """Rewrite the first tool result when the storm threshold is reached.

        Returns (tool_call_id, new_output, notice) when the first result should be patched.
        """
        sig, ok = batch_storm_signature(outcomes)
        if not ok:
            self.storm_sig = ""
            self.storm_count = 0
            return None
        if sig != self.storm_sig:
            self.storm_sig = sig
            self.storm_count = 1
            return None
        self.storm_count += 1
        if self.storm_count < self.threshold:
            return None

        first = outcomes[0]
        if len(outcomes) == 1:
            subject = f'"{first.tool_name}"'
            short = first.tool_name
        else:
            subject = f"this batch of {len(outcomes)} tool calls"
            short = f"a batch of {len(outcomes)} calls"
        appended = (
            f"\n\n{LOOP_GUARD_PREFIX} {subject} has now failed {self.storm_count} times in a row "
            "with the same error. Re-sending it — even with the wording changed — will not help: "
            "the calls keep failing the same way. Change approach: if an argument is being truncated, "
            "write less in one call and split the work into several smaller calls; otherwise fix the "
            "arguments, use a different tool, or explain the blocker in your final answer."
        )
        notice = f"loop guard: {short} failed {self.storm_count}× the same way — nudging the model to change approach"
        return first.tool_call_id, first.output + appended, notice


def classify_turn_outcome(
    tool_call_id: str,
    tool_name: str,
    result: str,
    *,
    blocked: bool = False,
    loop_guard: LoopGuard | None = None,
) -> ToolTurnOutcome:
    guard = loop_guard or LoopGuard()
    if blocked:
        err = guard.extract_error(result) or "blocked"
        return ToolTurnOutcome(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            output=result,
            error_msg=err,
            blocked=True,
        )
    error_msg = guard.error_from_result(result) or ""
    return ToolTurnOutcome(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        output=result,
        error_msg=error_msg,
    )


@dataclass
class RepeatSuccessGuard:
    """Blocks identical write-like successes within one user turn."""

    threshold: int = REPEAT_SUCCESS_THRESHOLD
    _counts: dict[str, int] = field(default_factory=dict)

    def reset(self) -> None:
        self._counts.clear()

    @staticmethod
    def _signature(tool_name: str, arguments: dict[str, Any]) -> str | None:
        if tool_name in WRITE_LIKE_TOOLS:
            return f"{tool_name}:{stable_json_dumps(arguments)}"
        if tool_name == "run_command" and not arguments.get("run_in_background"):
            command = str(arguments.get("command", "")).strip()
            if command:
                return f"run_command:{command}"
        return None

    def should_block(self, tool_name: str, arguments: dict[str, Any]) -> str | None:
        sig = self._signature(tool_name, arguments)
        if not sig:
            return None
        count = self._counts.get(sig, 0)
        if count < self.threshold:
            return None
        return (
            f"{LOOP_GUARD_PREFIX} Tool `{tool_name}` already succeeded {count} times with the same "
            "arguments in this turn. Change approach: verify with a read/test command or explain the blocker."
        )

    def record_success(self, tool_name: str, arguments: dict[str, Any]) -> None:
        sig = self._signature(tool_name, arguments)
        if sig:
            self._counts[sig] = self._counts.get(sig, 0) + 1


MAX_EMPTY_FINAL_BLOCKS = 3
MAX_EXECUTOR_HANDOFF_NUDGES = 1


def has_visible_final_answer(text: str) -> bool:
    return bool(text.strip())


def empty_final_notice(
    model: str,
    *,
    finish_reason: str = "unknown",
    reasoning_len: int = 0,
) -> str:
    return (
        f"empty final answer blocked: {model} returned no visible answer text "
        f"(finish={finish_reason}, reasoning={reasoning_len} chars); retrying"
    )


def empty_final_retry_message() -> str:
    return (
        "The previous assistant response finished without any visible answer text. "
        "Continue the same task now and provide a concise visible answer to the user. "
        "Do not send reasoning only."
    )


def finish_reason_notice(usage: dict[str, Any] | None) -> str | None:
    """Map abnormal finish_reason values to user-facing notices."""
    if not usage:
        return None
    reason = str(usage.get("finish_reason", ""))
    if reason == "length":
        return "response truncated: hit max output tokens"
    if reason == "content_filter":
        return "response blocked by content filter"
    if reason == "repetition_truncation":
        return "response truncated: model repetition detected"
    return None
