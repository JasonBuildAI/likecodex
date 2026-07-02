"""Shared turn preparation for all engine HTTP entry points."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from likecodex_engine.agent.commands import ExpandedPrompt, expand_prompt
from likecodex_engine.agent.coordinator import Coordinator
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.agent.plan_state import PlanState
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse


@dataclass
class PreparedTurn:
    """Result of preprocessing a user prompt before agent execution."""

    sid: str
    prompt: str
    expanded: ExpandedPrompt
    context: ContextManager
    runner: AgentLoop | Coordinator
    loop: AgentLoop
    early_responses: list[LLMResponse]
    plan_events: list[LLMResponse]


def _plan_mode_event(state: PlanState, reason: str) -> LLMResponse:
    return LLMResponse(
        content="",
        model="system",
        event_type="plan_mode_changed",
        metadata={
            "active": state.active,
            "pending_exit": state.pending_exit,
            "reason": reason,
        },
    )


def apply_plan_state(
    expanded: ExpandedPrompt,
    runner: AgentLoop | Coordinator,
    working_dir: str = ".",
) -> list[LLMResponse]:
    """Apply plan-mode transitions and emit plan_mode_changed events."""
    events: list[LLMResponse] = []
    state = runner.plan_state

    if expanded.plan_mode_enter:
        state.enter()
        events.append(_plan_mode_event(state, "enter"))
    if expanded.plan_mode_exit_request:
        state.request_exit(expanded.prompt)
        events.append(_plan_mode_event(state, "exit_requested"))
    if expanded.plan_mode_exit_approve:
        state.approve_exit()
        events.append(_plan_mode_event(state, "exit_approved"))

    goal = getattr(runner, "goal_state", None)
    if goal is not None:
        if expanded.goal_clear:
            goal.clear()
        if expanded.goal_start:
            goal.start(expanded.goal_start, expanded.goal_strategy)
            if expanded.goal_strategy == "research":
                from likecodex_engine.agent.autoresearch import init_research_state, research_run_dir

                run_dir = research_run_dir(working_dir)
                init_research_state(run_dir, expanded.goal_start)

    return events


def prepare_turn(
    *,
    sid: str,
    prompt: str,
    working_dir: str,
    context: ContextManager,
    runner: AgentLoop | Coordinator,
    loop: AgentLoop,
) -> PreparedTurn:
    """Expand prompt, inject @-refs, and apply plan-mode transitions."""
    expanded = expand_prompt(prompt, working_dir)
    early: list[LLMResponse] = []
    plan_events = apply_plan_state(expanded, runner, working_dir)
    early.extend(plan_events)

    if expanded.direct_reply is not None:
        early.append(
            LLMResponse(
                content=expanded.direct_reply,
                model="command",
                event_type="assistant",
            )
        )

    for block in expanded.context_blocks:
        context.add_context_block(block)

    return PreparedTurn(
        sid=sid,
        prompt=expanded.prompt,
        expanded=expanded,
        context=context,
        runner=runner,
        loop=loop,
        early_responses=early,
        plan_events=plan_events,
    )


async def run_manual_compact_responses(
    context: ContextManager,
    llm: Any,
    focus: str,
) -> AsyncIterator[LLMResponse]:
    """Yield compaction SSE events for /compact slash command."""
    if hasattr(context, "set_compact_llm"):
        context.set_compact_llm(llm)
    if not hasattr(context, "compact_async"):
        yield LLMResponse(
            content="Compaction is not available for this session context.",
            model="command",
            event_type="assistant",
        )
        return

    yield LLMResponse(
        content='{"trigger": "manual"}',
        model="system",
        event_type="compaction_started",
        metadata={"trigger": "manual", "focus": focus},
    )
    info = await context.compact_async(instructions=focus, force=True)
    compacted = info.get("compacted") if isinstance(info, dict) else False
    yield LLMResponse(
        content=str(info),
        model="system",
        event_type="compaction_done",
        metadata=info if isinstance(info, dict) else {},
    )
    if compacted:
        reply = "Context compacted."
        if focus:
            reply += f" Focus: {focus}"
    else:
        reply = "Nothing to compact."
    yield LLMResponse(content=reply, model="command", event_type="assistant")
