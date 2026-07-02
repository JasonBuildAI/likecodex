"""Loop configuration constants extracted from loop.py's hardcoded values."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoopConfig:
    """Centralised configuration constants for the agent loop.

    Replaces the hard-coded magic numbers that were scattered across
    ``_run_inner``, ``streaming.py`` and ``guards.py`` so they can be
    tuned from a single place.
    """

    # ── iteration limits ──────────────────────────────────────────────
    max_iterations: int = 0
    """Maximum number of model-turn iterations per ``run()`` call.
    0 means unlimited."""

    # ── watchdog / idle detection ─────────────────────────────────────
    watchdog_timeout: float = 300.0
    """Total wall-clock seconds before the loop is forcefully terminated."""
    watchdog_interval: float = 15.0
    """How often (seconds) watchdog checks are performed."""
    idle_timeout: float = 60.0
    """Seconds of inactivity before an idle nudge is emitted."""

    # ── stream recovery ───────────────────────────────────────────────
    max_stream_recoveries: int = 8
    """How many times a single model turn may be recovered on interruption."""

    # ── guard thresholds ──────────────────────────────────────────────
    max_empty_final_blocks: int = 3
    """Consecutive empty final-answer blocks before forced stop / downgrade."""
    max_executor_handoff_nudges: int = 1
    """How many times the executor hand-off guard may nudge the model."""
    max_final_readiness_blocks: int = 3
    """How many times final-readiness can block termination."""
    no_tool_termination_threshold: int = 3
    """Consecutive turns without tool calls → smart termination."""
    all_done_termination_threshold: int = 3
    """``[all done|finished|…]`` repetitions → smart termination."""

    # ── degradation escalation ────────────────────────────────────────
    max_sandbox_fallbacks: int = 3
    """Sandbox fallback count before degradation auto-escalates."""

    # ── plan / subagent ───────────────────────────────────────────────
    default_subagent_steps_ratio: float = 0.5
    """Fraction of parent ``max_iterations`` for sub-agent step limit."""

    # ── internal back-off (stream recovery) ───────────────────────────
    stream_backoff_schedule: list[float] = field(
        default_factory=lambda: [1, 2, 4, 8, 16, 30, 60, 120],
    )
    """Back-off delays (seconds) for stream-recovery attempts."""
