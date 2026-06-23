"""Agent mode tri-state tests — Ask / Agent / Manual.

Covers ModeManager transitions, tool permission checks,
permission-level mapping, and state preservation across switches.
"""

from __future__ import annotations

import pytest
from likecodex_engine.agent.mode_manager import (
    DANGEROUS_TOOLS,
    READ_ONLY_TOOLS,
    WRITE_TOOLS,
    AgentMode,
    ModeManager,
    ModeTransition,
    PermissionLevel,
    TransitionReason,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ask_manager() -> ModeManager:
    """ModeManager initialised in Ask mode."""
    return ModeManager(AgentMode.ASK)


@pytest.fixture
def agent_manager() -> ModeManager:
    """ModeManager initialised in Agent mode."""
    return ModeManager(AgentMode.AGENT)


@pytest.fixture
def manual_manager() -> ModeManager:
    """ModeManager initialised in Manual mode."""
    return ModeManager(AgentMode.MANUAL)


@pytest.fixture
def agent_auto_escalate() -> ModeManager:
    """Agent-mode manager with auto_escalate enabled."""
    return ModeManager(AgentMode.AGENT, auto_escalate=True)


# ---------------------------------------------------------------------------
# Ask mode
# ---------------------------------------------------------------------------

def test_ask_mode_blocks_write_operations(ask_manager: ModeManager) -> None:
    """Ask 模式下尝试修改文件应被拦截 — can_auto_execute returns False for all write tools."""
    for tool in WRITE_TOOLS:
        assert ask_manager.can_auto_execute(tool) is False, f"Ask mode should block write tool {tool!r}"


def test_ask_mode_allows_read_operations(ask_manager: ModeManager) -> None:
    """Ask 模式下读取文件无需确认 — can_auto_execute returns True for all read-only tools."""
    for tool in READ_ONLY_TOOLS:
        assert ask_manager.can_auto_execute(tool) is True, f"Ask mode should allow read tool {tool!r}"


def test_ask_mode_permission_level(ask_manager: ModeManager) -> None:
    """Ask mode maps to READ_ONLY permission level."""
    assert ask_manager.permission_level == PermissionLevel.READ_ONLY


def test_ask_mode_check_tool_permission_write(ask_manager: ModeManager) -> None:
    """Ask mode reports MANUAL_APPROVE for write tools."""
    for tool in WRITE_TOOLS:
        level = ask_manager.check_tool_permission(tool)
        assert level == PermissionLevel.MANUAL_APPROVE, f"Ask mode should require MANUAL_APPROVE for {tool!r}"


# ---------------------------------------------------------------------------
# Agent mode
# ---------------------------------------------------------------------------

def test_agent_mode_auto_executes_read(agent_manager: ModeManager) -> None:
    """Agent 模式下读取文件自动执行."""
    for tool in READ_ONLY_TOOLS:
        assert agent_manager.can_auto_execute(tool) is True, f"Agent mode should auto-execute read tool {tool!r}"


def test_agent_mode_auto_executes_single_file_edit(agent_manager: ModeManager) -> None:
    """Agent 模式下编辑单文件自动执行 — write tools (non-dangerous) are auto-executed."""
    single_file_write_tools = WRITE_TOOLS - DANGEROUS_TOOLS
    for tool in single_file_write_tools:
        assert agent_manager.can_auto_execute(tool) is True, f"Agent mode should auto-execute {tool!r}"


def test_agent_mode_dangerous_tools_blocked_without_escalate(agent_manager: ModeManager) -> None:
    """Agent mode without auto_escalate blocks dangerous tools."""
    for tool in DANGEROUS_TOOLS:
        assert not agent_manager.can_auto_execute(tool), (
            f"Agent mode should block dangerous tool {tool!r} without auto_escalate"
        )


def test_agent_mode_dangerous_tools_allowed_with_escalate(agent_auto_escalate: ModeManager) -> None:
    """Agent mode with auto_escalate allows dangerous tools."""
    for tool in DANGEROUS_TOOLS:
        assert agent_auto_escalate.can_auto_execute(tool) is True, f"auto_escalate should allow {tool!r}"


def test_agent_mode_requires_batch_approval_for_multi_file(agent_manager: ModeManager) -> None:
    """Agent 模式下编辑多文件触发批量确认 — multi_edit is a write tool that is auto-executed in Agent mode,
    but check_tool_permission reports AUTO_APPROVE indicating it goes through the approval pipeline."""
    level = agent_manager.check_tool_permission("multi_edit", {"edits": [{"path": "a.py"}, {"path": "b.py"}]})
    assert level == PermissionLevel.AUTO_APPROVE


def test_agent_mode_permission_level(agent_manager: ModeManager) -> None:
    """Agent mode maps to AUTO_APPROVE permission level."""
    assert agent_manager.permission_level == PermissionLevel.AUTO_APPROVE


# ---------------------------------------------------------------------------
# Manual mode
# ---------------------------------------------------------------------------

def test_manual_mode_requires_approval_for_all_writes(manual_manager: ModeManager) -> None:
    """Manual 模式下所有写操作均需逐个确认."""
    for tool in WRITE_TOOLS:
        assert manual_manager.can_auto_execute(tool) is False, f"Manual mode should block write tool {tool!r}"


def test_manual_mode_allows_read_operations(manual_manager: ModeManager) -> None:
    """Manual mode still allows read-only tools without confirmation."""
    for tool in READ_ONLY_TOOLS:
        assert manual_manager.can_auto_execute(tool) is True, f"Manual mode should allow read tool {tool!r}"


def test_manual_mode_permission_level(manual_manager: ModeManager) -> None:
    """Manual mode maps to MANUAL_APPROVE permission level."""
    assert manual_manager.permission_level == PermissionLevel.MANUAL_APPROVE


def test_manual_mode_check_tool_permission(manual_manager: ModeManager) -> None:
    """Manual mode reports MANUAL_APPROVE for all write tools."""
    for tool in WRITE_TOOLS:
        level = manual_manager.check_tool_permission(tool)
        assert level == PermissionLevel.MANUAL_APPROVE


# ---------------------------------------------------------------------------
# Mode transitions
# ---------------------------------------------------------------------------

def test_mode_switch_preserves_state(ask_manager: ModeManager) -> None:
    """模式切换后状态正确保持 — history is preserved and mode updates correctly."""
    assert ask_manager.mode == AgentMode.ASK

    transition = ask_manager.set_mode(AgentMode.AGENT, reason=TransitionReason.USER_REQUEST)
    assert ask_manager.mode == AgentMode.AGENT
    assert transition.from_mode == AgentMode.ASK
    assert transition.to_mode == AgentMode.AGENT
    assert ask_manager.permission_level == PermissionLevel.AUTO_APPROVE

    # Switch again
    ask_manager.set_mode(AgentMode.MANUAL, reason=TransitionReason.SAFETY_FALLBACK)
    assert ask_manager.mode == AgentMode.MANUAL
    assert ask_manager.permission_level == PermissionLevel.MANUAL_APPROVE

    # History should contain init + 2 transitions
    assert len(ask_manager.history) == 3
    assert ask_manager.history[0].reason == TransitionReason.SESSION_INIT


def test_mode_switch_noop_same_mode(ask_manager: ModeManager) -> None:
    """Switching to the same mode is a no-op and returns the last transition."""
    last = ask_manager.history[-1]
    returned = ask_manager.set_mode(AgentMode.ASK)
    assert returned is last
    assert len(ask_manager.history) == 1  # no new entry


def test_escalate_to_agent(ask_manager: ModeManager) -> None:
    """escalate_to_agent shortcut switches to Agent with AUTO_CLASSIFY reason."""
    t = ask_manager.escalate_to_agent(intent="edit_file")
    assert ask_manager.mode == AgentMode.AGENT
    assert t.reason == TransitionReason.AUTO_CLASSIFY
    assert t.metadata == {"intent": "edit_file"}


def test_fallback_to_manual(agent_manager: ModeManager) -> None:
    """fallback_to_manual shortcut switches to Manual with SAFETY_FALLBACK reason."""
    t = agent_manager.fallback_to_manual(trigger="rm -rf")
    assert agent_manager.mode == AgentMode.MANUAL
    assert t.reason == TransitionReason.SAFETY_FALLBACK
    assert t.metadata == {"trigger": "rm -rf"}


# ---------------------------------------------------------------------------
# Permission level mapping
# ---------------------------------------------------------------------------

def test_permission_level_mapping() -> None:
    """权限级别映射正确性 — all three modes map correctly and inversely."""
    expected = {
        AgentMode.ASK: PermissionLevel.READ_ONLY,
        AgentMode.AGENT: PermissionLevel.AUTO_APPROVE,
        AgentMode.MANUAL: PermissionLevel.MANUAL_APPROVE,
    }
    for mode, level in expected.items():
        mgr = ModeManager(mode)
        assert mgr.permission_level == level

    # Inverse: every PermissionLevel maps back to a valid AgentMode
    for level in PermissionLevel:
        mgr = ModeManager(AgentMode.ASK)
        mgr.set_mode({
            PermissionLevel.READ_ONLY: AgentMode.ASK,
            PermissionLevel.AUTO_APPROVE: AgentMode.AGENT,
            PermissionLevel.MANUAL_APPROVE: AgentMode.MANUAL,
        }[level])
        assert mgr.permission_level == level


# ---------------------------------------------------------------------------
# Tool classification helpers
# ---------------------------------------------------------------------------

def test_is_read_only_tool() -> None:
    """Static helper correctly identifies read-only tools."""
    assert ModeManager.is_read_only_tool("read_file") is True
    assert ModeManager.is_read_only_tool("lsp_hover") is True
    assert ModeManager.is_read_only_tool("write_file") is False
    assert ModeManager.is_read_only_tool("run_command") is False


def test_is_write_tool() -> None:
    """Static helper correctly identifies write tools."""
    assert ModeManager.is_write_tool("write_file") is True
    assert ModeManager.is_write_tool("edit_file") is True
    assert ModeManager.is_write_tool("read_file") is False


def test_is_dangerous_tool() -> None:
    """Static helper correctly identifies dangerous tools."""
    assert ModeManager.is_dangerous_tool("run_command") is True
    assert ModeManager.is_dangerous_tool("read_file") is False


def test_unknown_tool_requires_manual_approval(ask_manager: ModeManager) -> None:
    """Unknown tools default to MANUAL_APPROVE in check_tool_permission."""
    assert ask_manager.check_tool_permission("unknown_tool_xyz") == PermissionLevel.MANUAL_APPROVE
    assert ask_manager.can_auto_execute("unknown_tool_xyz") is False


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def test_mode_change_callback_fires() -> None:
    """on_mode_change callback fires on transition."""
    mgr = ModeManager(AgentMode.ASK)
    events: list[ModeTransition] = []
    mgr.on_mode_change(lambda t: events.append(t))

    mgr.set_mode(AgentMode.AGENT)
    assert len(events) == 1
    assert events[0].from_mode == AgentMode.ASK
    assert events[0].to_mode == AgentMode.AGENT


def test_callback_exception_does_not_break_transition() -> None:
    """A failing callback does not prevent the mode transition."""
    mgr = ModeManager(AgentMode.ASK)
    mgr.on_mode_change(lambda _: (_ for _ in ()).throw(RuntimeError("boom")))

    mgr.set_mode(AgentMode.AGENT)
    assert mgr.mode == AgentMode.AGENT


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def test_to_dict_snapshot(ask_manager: ModeManager) -> None:
    """to_dict returns a serialisable snapshot of the manager state."""
    d = ask_manager.to_dict()
    assert d["mode"] == "ask"
    assert d["permission_level"] == "read_only"
    assert isinstance(d["history"], list)
    assert len(d["history"]) == 1  # SESSION_INIT only


# ---------------------------------------------------------------------------
# String initialisation
# ---------------------------------------------------------------------------

def test_string_mode_initialisation() -> None:
    """ModeManager accepts string mode values."""
    mgr = ModeManager("agent")
    assert mgr.mode == AgentMode.AGENT


def test_invalid_mode_raises() -> None:
    """Invalid mode string raises ValueError."""
    with pytest.raises(ValueError):
        ModeManager("invalid_mode")


# ---------------------------------------------------------------------------
# Auto-escalate property
# ---------------------------------------------------------------------------

def test_auto_escalate_setter() -> None:
    """auto_escalate can be toggled at runtime."""
    mgr = ModeManager(AgentMode.AGENT)
    assert mgr.auto_escalate is False
    mgr.auto_escalate = True
    assert mgr.auto_escalate is True
    assert mgr.can_auto_execute("run_command") is True
