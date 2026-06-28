"""Agent mode state machine — manages Ask / Agent / Manual tri-state transitions.

Mirrors Cursor's automation model:
- **Ask**    : read-only tools, answers questions without modifying code.
- **Agent**  : fully automatic execution with minimal confirmation.
- **Manual** : full tool chain but every write requires explicit user approval.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

from likecodex_engine.tools.cache import READ_TOOLS as _CACHE_READ_TOOLS, WRITE_TOOLS as _CACHE_WRITE_TOOLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentMode(StrEnum):
    """The three core interaction modes (Cursor-parity)."""
    ASK = "ask"          # Read-only, no code mutations
    AGENT = "agent"      # Fully automated, minimal prompts
    MANUAL = "manual"    # Full tools, every write needs approval


class PermissionLevel(StrEnum):
    """Granular permission tiers that map onto the three modes."""
    READ_ONLY = "read_only"       # Only read / search tools
    AUTO_APPROVE = "auto_approve" # Reads + writes auto-approved (Agent)
    MANUAL_APPROVE = "manual_approve"  # Every write needs user OK (Manual)


class TransitionReason(StrEnum):
    """Why a mode transition happened."""
    USER_REQUEST = "user_request"
    AUTO_CLASSIFY = "auto_classify"   # e.g. intent classifier detected edit
    SAFETY_FALLBACK = "safety_fallback"  # dangerous op → Manual
    SESSION_INIT = "session_init"
    TIMEOUT = "timeout"


# ---------------------------------------------------------------------------
# Mode transition event
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModeTransition:
    """Immutable record of a single mode change."""
    from_mode: AgentMode
    to_mode: AgentMode
    reason: TransitionReason
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Permission-level ↔ mode mapping
# ---------------------------------------------------------------------------

_MODE_TO_PERMISSION: dict[AgentMode, PermissionLevel] = {
    AgentMode.ASK: PermissionLevel.READ_ONLY,
    AgentMode.AGENT: PermissionLevel.AUTO_APPROVE,
    AgentMode.MANUAL: PermissionLevel.MANUAL_APPROVE,
}

_PERMISSION_TO_MODE: dict[PermissionLevel, AgentMode] = {
    v: k for k, v in _MODE_TO_PERMISSION.items()
}


# ---------------------------------------------------------------------------
# Tool classification helpers
# ---------------------------------------------------------------------------

# Tools that never mutate state — always safe in any mode.
READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "read_file",
    "list_dir",
    "ls",
    "glob",
    "search_files",
    "grep_files",
    "git_status",
    "git_diff",
    "git_log",
    "git_branch",
    "web_fetch",
    "web_search",
    "history",
    "memory_search",
    "memory",
    "code_index",
    "ask",
    "lsp_hover",
    "lsp_completion",
    "lsp_definition",
    "lsp_references",
    "lsp_diagnostics",
    "lsp_symbols",
})

# Tools that mutate state — require elevated permission.
# Reuse the canonical set from cache.py (frozenset for immutability).
WRITE_TOOLS: frozenset[str] = frozenset(_CACHE_WRITE_TOOLS)

# Especially dangerous operations that force Manual mode.
DANGEROUS_TOOLS: frozenset[str] = frozenset({
    "run_command",   # shell commands can be destructive
})


# ---------------------------------------------------------------------------
# ModeManager
# ---------------------------------------------------------------------------

# Type alias for callbacks fired on mode transitions.
ModeChangeCallback = Callable[[ModeTransition], None]


class ModeManager:
    """Central state machine that tracks the current AgentMode and
    orchestrates transitions between Ask / Agent / Manual.

    Parameters
    ----------
    initial_mode:
        Starting mode.  Defaults to ``AgentMode.ASK``.
    auto_escalate:
        When *True*, automatically escalate to ``Agent`` when an edit intent
        is detected (e.g. via an intent classifier).  Defaults to *False*.
    """

    def __init__(
        self,
        initial_mode: AgentMode | str = AgentMode.ASK,
        *,
        auto_escalate: bool = False,
    ) -> None:
        self._mode = AgentMode(initial_mode)
        self._auto_escalate = auto_escalate
        self._history: list[ModeTransition] = []
        self._callbacks: list[ModeChangeCallback] = []

        # Record the initial transition
        self._history.append(
            ModeTransition(
                from_mode=self._mode,
                to_mode=self._mode,
                reason=TransitionReason.SESSION_INIT,
            )
        )

    # -- Properties ---------------------------------------------------------

    @property
    def mode(self) -> AgentMode:
        """The current interaction mode."""
        return self._mode

    @property
    def permission_level(self) -> PermissionLevel:
        """The permission level that corresponds to the current mode."""
        return _MODE_TO_PERMISSION[self._mode]

    @property
    def history(self) -> list[ModeTransition]:
        """Full transition history (oldest first)."""
        return list(self._history)

    @property
    def auto_escalate(self) -> bool:
        return self._auto_escalate

    @auto_escalate.setter
    def auto_escalate(self, value: bool) -> None:
        self._auto_escalate = value

    # -- Mode transitions ---------------------------------------------------

    def set_mode(
        self,
        new_mode: AgentMode | str,
        *,
        reason: TransitionReason = TransitionReason.USER_REQUEST,
        metadata: dict[str, Any] | None = None,
    ) -> ModeTransition:
        """Explicitly switch to *new_mode*.

        Returns the :class:`ModeTransition` record.
        """
        new_mode = AgentMode(new_mode)
        if new_mode == self._mode:
            # No-op, but still return the current transition record
            return self._history[-1]

        transition = ModeTransition(
            from_mode=self._mode,
            to_mode=new_mode,
            reason=reason,
            metadata=metadata or {},
        )
        self._history.append(transition)
        old = self._mode
        self._mode = new_mode
        logger.info("Mode transition: %s → %s (%s)", old.value, new_mode.value, reason.value)
        self._fire_callbacks(transition)
        return transition

    def escalate_to_agent(self, **meta: Any) -> ModeTransition:
        """Shortcut: escalate to Agent mode (e.g. after intent classification)."""
        return self.set_mode(
            AgentMode.AGENT,
            reason=TransitionReason.AUTO_CLASSIFY,
            metadata=meta,
        )

    def fallback_to_manual(self, **meta: Any) -> ModeTransition:
        """Safety fallback: force Manual mode (e.g. after dangerous op detected)."""
        return self.set_mode(
            AgentMode.MANUAL,
            reason=TransitionReason.SAFETY_FALLBACK,
            metadata=meta,
        )

    # -- Tool-call permission check -----------------------------------------

    def can_auto_execute(self, tool_name: str) -> bool:
        """Return *True* if *tool_name* may execute without user confirmation
        under the current mode."""
        # Read-only tools are always allowed
        if self.is_read_only_tool(tool_name):
            return True

        if self._mode == AgentMode.AGENT:
            # Agent mode auto-executes everything except explicitly dangerous
            return tool_name not in DANGEROUS_TOOLS or self._auto_escalate

        # Ask and Manual modes require confirmation for writes
        return False

    def check_tool_permission(self, tool_name: str, arguments: dict[str, Any] | None = None) -> PermissionLevel:
        """Determine the required permission level for a tool call.

        This does **not** grant or deny — it reports what level is needed.
        """
        if self.is_read_only_tool(tool_name):
            return PermissionLevel.READ_ONLY

        if tool_name in DANGEROUS_TOOLS:
            return PermissionLevel.MANUAL_APPROVE

        if tool_name in WRITE_TOOLS:
            if self._mode == AgentMode.AGENT:
                return PermissionLevel.AUTO_APPROVE
            return PermissionLevel.MANUAL_APPROVE

        # Unknown tools default to manual approval
        return PermissionLevel.MANUAL_APPROVE

    # -- Callbacks ----------------------------------------------------------

    def on_mode_change(self, callback: ModeChangeCallback) -> None:
        """Register a callback invoked on every mode transition."""
        self._callbacks.append(callback)

    def _fire_callbacks(self, transition: ModeTransition) -> None:
        for cb in self._callbacks:
            try:
                cb(transition)
            except Exception:
                logger.exception("Error in mode-change callback %s", cb)

    # -- Classification helpers ---------------------------------------------

    @staticmethod
    def is_read_only_tool(tool_name: str) -> bool:
        return tool_name in READ_ONLY_TOOLS or tool_name.startswith("lsp_")

    @staticmethod
    def is_write_tool(tool_name: str) -> bool:
        return tool_name in WRITE_TOOLS

    @staticmethod
    def is_dangerous_tool(tool_name: str) -> bool:
        return tool_name in DANGEROUS_TOOLS

    # -- Serialisation helpers ----------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Snapshot the manager state (useful for persistence / debugging)."""
        return {
            "mode": self._mode.value,
            "permission_level": self.permission_level.value,
            "auto_escalate": self._auto_escalate,
            "history": [
                {
                    "from": t.from_mode.value,
                    "to": t.to_mode.value,
                    "reason": t.reason.value,
                    "timestamp": t.timestamp,
                    "metadata": t.metadata,
                }
                for t in self._history
            ],
        }

    def __repr__(self) -> str:
        return f"ModeManager(mode={self._mode.value!r}, history_len={len(self._history)})"
