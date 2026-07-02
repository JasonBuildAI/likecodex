"""AgentLoop 状态机重构 — 纯数据驱动，不含 Agent 具体业务逻辑。"""

from __future__ import annotations

import asyncio
import enum
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class AgentState(enum.StrEnum):
    """Agent 有限状态机中的全部状态枚举。"""

    IDLE = "idle"
    RUNNING = "running"
    WAITING_TOOL = "waiting_tool"
    EXECUTING_TOOLS = "executing_tools"
    COMPACTING = "compacting"
    STREAM_RECOVERY = "stream_recovery"
    DEGRADED = "degraded"
    ERROR = "error"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class StateTransition:
    """定义一条状态转换规则。

    Attributes:
        from_state: 源状态。
        to_state: 目标状态。
        trigger: 触发本次转换的事件名称。
        guard: 可选的条件函数，返回 True 时才允许转换。
        action: 可选的回调，转换成功后被调用。
    """

    from_state: AgentState
    to_state: AgentState
    trigger: str
    guard: Callable[[dict[str, Any] | None], bool] | None = None
    action: Callable[[dict[str, Any] | None], Any] | None = None


class InvalidTransitionError(Exception):
    """当尝试一个不存在或 guard 拒绝的状态转换时抛出。"""

    def __init__(
        self,
        current: AgentState,
        trigger: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.current = current
        self.trigger = trigger
        self.context = context
        super().__init__(
            f"Invalid transition: no rule for trigger '{trigger}' "
            f"from state '{current.value}'"
        )


class StateMachine:
    """通用的异步协程安全有限状态机。

    职责:
    - 维护状态转换表 (transition table)
    - 执行异步状态转换，附带 guard 检验与 action 回调
    - 记录转换历史，支持调试与回放
    - 提供事件监听机制
    """

    def __init__(self, initial_state: AgentState = AgentState.IDLE) -> None:
        self._states: dict[AgentState, list[StateTransition]] = {}
        self._current_state: AgentState = initial_state
        self._history: list[tuple[AgentState, AgentState, str, float]] = []
        self._listeners: dict[str, list[Callable[..., Any]]] = {}
        self._lock = asyncio.Lock()

    # -- 构建转换表 --

    def add_transition(
        self,
        from_state: AgentState,
        to_state: AgentState,
        trigger: str,
        guard: Callable[[dict[str, Any] | None], bool] | None = None,
        action: Callable[[dict[str, Any] | None], Any] | None = None,
    ) -> None:
        """注册一条状态转换规则。

        Args:
            from_state: 源状态。
            to_state: 目标状态。
            trigger: 触发事件名称。
            guard: 可选条件函数，接收 context 返回 bool。
            action: 可选回调，转换成功后执行。
        """
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            guard=guard,
            action=action,
        )
        self._states.setdefault(from_state, []).append(transition)

    # -- 核心转换 --

    async def transition(
        self,
        trigger: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """执行一次状态转换。

        流程:
        1. 从当前状态查找匹配 trigger 的转换规则
        2. 如有多条，逐一检查 guard (无 guard 或 guard 返回 True 的优先)
        3. 执行 action 回调 (如果有)
        4. 更新当前状态
        5. 记录历史
        6. 触发事件监听器

        Args:
            trigger: 事件名称。
            context: 透传给 guard 和 action 的上下文数据。

        Returns:
            转换成功返回 True，否则返回 False。

        Raises:
            InvalidTransitionError: 没有匹配规则或 guard 全部拒绝。
        """
        async with self._lock:
            candidates = self._states.get(self._current_state, [])
            matched: StateTransition | None = None

            for t in candidates:
                if t.trigger != trigger:
                    continue
                if t.guard is not None:
                    if t.guard(context):
                        matched = t
                        break
                else:
                    matched = t
                    break

            if matched is None:
                has_trigger_match = any(t.trigger == trigger for t in candidates)
                if has_trigger_match:
                    return False
                raise InvalidTransitionError(self._current_state, trigger, context)

            from_state = self._current_state
            self._current_state = matched.to_state
            now = time.time()
            self._history.append((from_state, matched.to_state, trigger, now))

            if matched.action is not None:
                if asyncio.iscoroutinefunction(matched.action):
                    await matched.action(context)
                else:
                    matched.action(context)

            self._notify_listeners("transition", from_state, matched.to_state, trigger)
            self._notify_listeners(
                f"enter_state:{matched.to_state.value}",
                from_state,
                matched.to_state,
                trigger,
            )

            return True

    # -- 查询 --

    def get_current_state(self) -> AgentState:
        """返回当前状态。"""
        return self._current_state

    def can_transition_to(self, target_state: AgentState) -> bool:
        """检查当前状态是否存在至少一条指向 target_state 的转换规则。"""
        candidates = self._states.get(self._current_state, [])
        return any(t.to_state == target_state for t in candidates)

    def get_history(self, limit: int = 10) -> list[tuple[AgentState, AgentState, str, float]]:
        """返回最近 N 条转换历史。

        Args:
            limit: 返回条数上限。

        Returns:
            [(from_state, to_state, trigger, timestamp), ...]
        """
        return self._history[-limit:] if self._history else []

    # -- 事件监听 --

    def on(self, event: str, callback: Callable[..., Any]) -> None:
        """注册事件监听器。

        内置事件:
        - ``transition``        -- 任意转换完成时
        - ``enter_state:<name>`` -- 进入特定状态时 (如 ``enter_state:running``)

        Args:
            event: 事件名称。
            callback: 回调函数。
        """
        self._listeners.setdefault(event, []).append(callback)

    # -- 重置 --

    def reset(self) -> None:
        """重置状态机为初始 IDLE 状态，清空历史。"""
        self._current_state = AgentState.IDLE
        self._history.clear()
        self._notify_listeners("reset")

    # -- 内部工具 --

    def _notify_listeners(self, event: str, *args: Any) -> None:
        for cb in self._listeners.get(event, []):
            try:
                cb(*args)
            except Exception:
                pass


def build_agent_state_machine() -> StateMachine:
    """构建完整的 Agent 状态转换表。"""
    sm = StateMachine(initial_state=AgentState.IDLE)

    # IDLE -> RUNNING
    sm.add_transition(AgentState.IDLE, AgentState.RUNNING, "start")

    # RUNNING -> 各种状态
    sm.add_transition(AgentState.RUNNING, AgentState.WAITING_TOOL, "tool_call_received")
    sm.add_transition(AgentState.RUNNING, AgentState.COMPLETED, "final_answer")
    sm.add_transition(AgentState.RUNNING, AgentState.ERROR, "error")
    sm.add_transition(AgentState.RUNNING, AgentState.STREAM_RECOVERY, "stream_failure")
    sm.add_transition(AgentState.RUNNING, AgentState.COMPACTING, "compaction_needed")
    sm.add_transition(AgentState.RUNNING, AgentState.DEGRADED, "degradation_triggered")
    sm.add_transition(AgentState.RUNNING, AgentState.CANCELLED, "cancel")

    # WAITING_TOOL -> EXECUTING_TOOLS / CANCELLED
    sm.add_transition(AgentState.WAITING_TOOL, AgentState.EXECUTING_TOOLS, "tools_ready")
    sm.add_transition(AgentState.WAITING_TOOL, AgentState.CANCELLED, "cancel")

    # EXECUTING_TOOLS -> RUNNING / ERROR / CANCELLED
    sm.add_transition(AgentState.EXECUTING_TOOLS, AgentState.RUNNING, "tools_completed")
    sm.add_transition(AgentState.EXECUTING_TOOLS, AgentState.ERROR, "tool_error")
    sm.add_transition(AgentState.EXECUTING_TOOLS, AgentState.CANCELLED, "cancel")

    # COMPACTING -> RUNNING / CANCELLED
    sm.add_transition(AgentState.COMPACTING, AgentState.RUNNING, "compaction_completed")
    sm.add_transition(AgentState.COMPACTING, AgentState.CANCELLED, "cancel")

    # STREAM_RECOVERY -> RUNNING / DEGRADED / CANCELLED
    sm.add_transition(AgentState.STREAM_RECOVERY, AgentState.RUNNING, "recovery_success")
    sm.add_transition(AgentState.STREAM_RECOVERY, AgentState.DEGRADED, "recovery_failed")
    sm.add_transition(AgentState.STREAM_RECOVERY, AgentState.CANCELLED, "cancel")

    # DEGRADED -> RUNNING / CANCELLED
    sm.add_transition(AgentState.DEGRADED, AgentState.RUNNING, "recovery")
    sm.add_transition(AgentState.DEGRADED, AgentState.CANCELLED, "cancel")

    # ERROR / COMPLETED / CANCELLED -> IDLE
    sm.add_transition(AgentState.ERROR, AgentState.IDLE, "reset")
    sm.add_transition(AgentState.COMPLETED, AgentState.IDLE, "reset")
    sm.add_transition(AgentState.CANCELLED, AgentState.IDLE, "reset")

    return sm
