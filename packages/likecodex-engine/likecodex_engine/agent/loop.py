"""Core agentic loop for LikeCodex."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator, Callable
import time
from typing import Any

import aiohttp

from likecodex_engine.agent.checkpoints import CheckpointManager
from likecodex_engine.agent.coordinator import EXECUTOR_HANDOFF_MARKER, should_plan
from likecodex_engine.agent.dispatch import execute_tool_calls_parallel
from likecodex_engine.agent.evidence import EvidenceLedger
from likecodex_engine.agent.goal import GoalState
from likecodex_engine.agent.guards import (
    MAX_EMPTY_FINAL_BLOCKS,
    MAX_EXECUTOR_HANDOFF_NUDGES,
    LoopGuard,
    RepeatSuccessGuard,
    StormBreaker,
    ToolCircuitBreaker,
    ToolTurnOutcome,
    classify_turn_outcome,
    empty_final_notice,
    empty_final_retry_message,
    finish_reason_notice,
    has_visible_final_answer,
)
from likecodex_engine.agent.output_limit import limit_tool_output
from likecodex_engine.agent.plan_mode import plan_mode_block_reason, plan_mode_tool_result
from likecodex_engine.agent.plan_state import PlanState
from likecodex_engine.agent.planner import Plan, Planner, PlanStep, StepStatus
from likecodex_engine.agent.readiness import final_readiness_check
from likecodex_engine.agent.streaming import (
    MAX_STREAM_RECOVERIES,
    StreamTurnResult,
    backoff_delay,
    stream_model_turn,
    stream_recovery_message,
)
from likecodex_engine.agent.subagent_registry import subagent_tool_registry
from likecodex_engine.context.cache_shape import (
    PrefixShape,
    compare_prefix_shape,
    format_usage_line,
)
from likecodex_engine.context.manager import ContextManager, stable_json_dumps, stable_tool_calls_json
from likecodex_engine.hooks.runner import fire_hooks
from likecodex_engine.llm.base import LLMProvider, LLMResponse
from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.llm.retry import retry_context
from likecodex_engine.llm.tool_repair import ensure_tool_call_ids, flatten_tool_schemas, merge_tool_calls
from likecodex_engine.memory.vector import VectorMemory
from likecodex_engine.permissions.evaluator import (
    ApprovalMode,
    ExecutionMode,
    PermissionEvaluator,
)
from likecodex_engine.tools.ask import AskToolHandler
from likecodex_engine.tools.registry import ToolRegistry


class AgentLoop:
    """The canonical loop: model -> tool calls -> results -> repeat."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        context: ContextManager,
        max_iterations: int = 0,
        planner: Planner | None = None,
        permission_evaluator: PermissionEvaluator | None = None,
        sandbox_executor_url: str | None = None,
        memory: VectorMemory | None = None,
        session_id: str | None = None,
        on_event: Callable[[LLMResponse], None] | None = None,
        agent_factory: Callable[[list[str] | None, int | None], AgentLoop] | None = None,
        no_tools: bool = False,
        checkpoints: CheckpointManager | None = None,
        plan_state: PlanState | None = None,
        goal_state: GoalState | None = None,
        is_subagent: bool = False,
        executor_handoff_guard: bool = False,
        agent_mode: str = "agent",
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.context = context
        self.max_iterations = max_iterations
        self.planner = planner
        self.permission_evaluator = permission_evaluator or PermissionEvaluator(ApprovalMode.AUTO)
        self.sandbox_executor_url = sandbox_executor_url or os.environ.get(
            "LIKECODEX_SANDBOX_URL", "http://127.0.0.1:8080/execute"
        )
        self.memory = memory
        self.session_id = session_id
        self.on_event = on_event
        self.agent_factory = agent_factory
        self.no_tools = no_tools
        self.agent_mode = agent_mode
        self.checkpoints = checkpoints or CheckpointManager(tools.working_dir)
        self.pending_permissions: dict[str, asyncio.Future[bool]] = {}
        self.loop_guard = LoopGuard()
        self.repeat_guard = RepeatSuccessGuard()
        self.storm_breaker = StormBreaker()
        self._turn_outcomes: list[ToolTurnOutcome] = []
        self.evidence = EvidenceLedger()
        self.project_checks: list[dict[str, Any]] = []
        self._final_readiness_blocks = 0
        self._empty_final_blocks = 0
        self.plan_state = plan_state or PlanState()
        self.goal_state = goal_state or GoalState()
        self.ask_handler = AskToolHandler()
        self.pending_asks: dict[str, asyncio.Future[str]] = {}
        self.interactive_ask = True
        self._plan_exec_window = False
        self._pending_grant_scope = "once"
        self.is_subagent = is_subagent
        self.executor_handoff_guard = executor_handoff_guard
        self._used_any_tool = False
        self._handoff_nudges = 0
        self._handoff_active = False
        self._mode_downgraded = False
        self._all_done_counter = 0
        self._no_tool_turns: int = 0
        self._watchdog_event: asyncio.Event | None = None
        self._last_activity_time: float = 0.0
        self.circuit_breaker = ToolCircuitBreaker()
        self._degradation_level: int = 0  # 0=normal, 1=no-write, 2=ask-mode, 3=text-only
        self._model_swap_attempted: bool = False
        self._sandbox_fallbacks: int = 0
        if hasattr(context, "set_working_dir"):
            context.set_working_dir(tools.working_dir)
        if hasattr(context, "set_compact_llm"):
            context.set_compact_llm(llm)
        tools.set_session_log_provider(lambda: self.context.messages)

    async def run(self, prompt: str) -> AsyncIterator[LLMResponse]:
        """Execute the loop for a single user prompt."""
        with retry_context():
            async for resp in self._run_with_retry_context(prompt):
                yield resp

    async def _run_with_retry_context(self, prompt: str) -> AsyncIterator[LLMResponse]:
        # Emit mode_changed event at start of run
        yield self._emit(
            LLMResponse(
                content="",
                model="system",
                event_type="mode_changed",
                metadata={"agent_mode": self.agent_mode},
            )
        )
        if self.memory:
            memories = self.memory.search(prompt, top_k=3)
            if memories:
                snippet = "\n".join(f"- {m.get('text', '')}" for m in memories)
                self.context.add_context_block(f"Relevant memory:\n{snippet}")

        # Inject reasoning_language transient block (not part of immutable prefix)
        reasoning_language = getattr(self, "_reasoning_language", "")
        if reasoning_language:
            self.context.add_context_block(f"<reasoning-language>{reasoning_language}</reasoning-language>")

        self.context.add_user_message(prompt)

        self.evidence.reset()
        self.repeat_guard.reset()
        self.storm_breaker.reset()
        self._turn_outcomes = []
        self._final_readiness_blocks = 0
        self._empty_final_blocks = 0
        self._used_any_tool = False
        self._no_tool_turns = 0
        self._handoff_nudges = 0
        self._handoff_active = self.executor_handoff_guard and EXECUTOR_HANDOFF_MARKER in prompt
        self.tools.set_evidence_ledger(self.evidence)

        hook_out = await fire_hooks(
            "UserPromptSubmit",
            self.tools.working_dir,
            {"prompt": prompt[:500]},
        )
        if hook_out:
            self.context.add_context_block(hook_out)

        goal_block = self.goal_state.transient_block()
        if goal_block:
            self.context.add_context_block(goal_block)

        plan: Plan | None = None
        use_planner = self.planner and should_plan(prompt) and not self.is_subagent
        if use_planner and self.planner:
            plan = await self.planner.plan(self.session_id or "task", prompt)
            if hasattr(self.context, "add_scratch"):
                self.context.add_scratch(plan.reasoning)
            plan_text = json.dumps(
                {
                    "reasoning": plan.reasoning,
                    "steps": [{"id": s.id, "description": s.description} for s in plan.steps],
                },
                sort_keys=True,
            )
            if hasattr(self.context, "add_plan_block"):
                self.context.add_plan_block(plan_text)
            else:
                self.context.add_context_block(f"Plan:\n{plan.reasoning}")
            yield self._emit(LLMResponse(content=plan.reasoning, model="planner", event_type="plan"))
            for step in plan.steps:
                yield self._emit(
                    LLMResponse(
                        content=json.dumps(
                            {
                                "step_id": step.id,
                                "description": step.description,
                                "status": step.status.value,
                            }
                        ),
                        model="planner",
                        event_type="plan",
                    )
                )

            parallel = self._parallelizable_steps(plan.steps)
            if parallel and self.agent_factory:
                from likecodex_engine.agent.subagent import SubAgentOrchestrator

                collected: list[LLMResponse] = []
                def _on_progress(p: dict[str, Any]) -> None:
                    collected.append(
                        LLMResponse(
                            content="",
                            model="subagent",
                            event_type="subagent_progress",
                            metadata=p,
                        )
                    )

                orchestrator = SubAgentOrchestrator(self.agent_factory, on_progress=_on_progress)
                results_task = asyncio.create_task(
                    orchestrator.run_parallel([(step.id, step.description) for step in parallel])
                )
                # Yield progress events as they come in
                while not results_task.done():
                    if collected:
                        evt = collected.pop(0)
                        yield self._emit(evt)
                    await asyncio.sleep(0.1)
                results = await results_task
                # Emit any remaining progress
                for evt in collected:
                    yield self._emit(evt)
                summary = SubAgentOrchestrator.summarize(results)
                self.context.add_context_block(f"Sub-agent results:\n{summary}")
                yield self._emit(LLMResponse(content=summary, model="subagent", event_type="subagent"))
                for step in parallel:
                    step.status = StepStatus.COMPLETED

            for step in plan.steps:
                if step.status == StepStatus.COMPLETED:
                    continue
                if not self._dependencies_met(step, plan.steps):
                    step.status = StepStatus.SKIPPED
                    continue
                step.status = StepStatus.IN_PROGRESS
                yield self._emit(
                    LLMResponse(
                        content=json.dumps({"step_id": step.id, "status": "in_progress"}),
                        model="planner",
                        event_type="plan",
                    )
                )
                async for resp in self._run_inner(step.description):
                    yield resp
                step.status = StepStatus.COMPLETED
                yield self._emit(
                    LLMResponse(
                        content=json.dumps({"step_id": step.id, "status": "completed"}),
                        model="planner",
                        event_type="plan",
                    )
                )
            if not plan.steps:
                async for resp in self._run_inner(prompt):
                    yield resp
        else:
            async for resp in self._run_inner(prompt):
                yield resp

        async for resp in self._run_goal_continuations():
            yield resp

        if self.memory:
            summary = self._summarize_conversation()
            if summary:
                self.memory.add(summary, {"session_id": self.session_id})

    async def _run_inner(self, prompt: str) -> AsyncIterator[LLMResponse]:
        if prompt and self.context.messages[-1].role.value != "user":
            self.context.add_user_message(prompt)

        self._plan_exec_window = self.plan_state.execution_window_active
        tool_schemas = [] if self.no_tools else flatten_tool_schemas(self.tools.to_openai_schema())
        # Apply degradation: strip write tools at level 1+, reduce to read-only at level 2+
        if self._degradation_level >= 1 and tool_schemas:
            degraded = [s for s in tool_schemas if self.tools.is_read_only(s.get("function", {}).get("name", ""))]
            if self._degradation_level >= 2:
                tool_schemas = degraded  # read-only only
            elif degraded:
                tool_schemas = degraded  # no write tools
        stream_recoveries = 0
        last_prefix_shape: PrefixShape | None = None
        have_last_prefix_shape = False

        # Start watchdog
        self._last_activity_time = time.time()
        self._watchdog_event = asyncio.Event()
        _watchdog_interval = 15  # seconds
        _watchdog_timeout = 300   # 5 minutes
        _loop_start_time = time.time()
        _watchdog_fired = False

        iteration = 0
        hit_max_iterations = False
        while True:
            if self.max_iterations > 0 and iteration >= self.max_iterations:
                hit_max_iterations = True
                break
            # Cache messages once per iteration to avoid redundant serialization
            _cached_messages = self.context.get_messages()
            messages = _cached_messages
            cur_prefix_shape = self._capture_prefix_shape(tool_schemas)
            response: LLMResponse | None = None

            while True:
                turn_result: StreamTurnResult | None = None
                async for event in stream_model_turn(
                    self.llm,
                    messages,
                    tool_schemas if tool_schemas else None,
                ):
                    if isinstance(event, StreamTurnResult):
                        turn_result = event
                    else:
                        yield self._emit(event)

                if turn_result is None:
                    break

                if turn_result.interrupted:
                    partial_text = turn_result.partial_text
                    if partial_text:
                        self.context.add_assistant_message(content=partial_text)
                    if stream_recoveries < MAX_STREAM_RECOVERIES:
                        stream_recoveries += 1
                        delay = backoff_delay(stream_recoveries)
                        await asyncio.sleep(delay)
                        recovery = stream_recovery_message(bool(partial_text), turn_result.partial_tool_started)
                        self.context.add_user_message(recovery)
                        yield self._emit(
                            LLMResponse(
                                content=recovery,
                                model="system",
                                event_type="retrying",
                                metadata={
                                    "retry_attempt": stream_recoveries,
                                    "retry_max": MAX_STREAM_RECOVERIES,
                                    "retry_delay_s": round(delay, 2),
                                    "reason": "stream_recovery",
                                },
                            )
                        )
                        messages = self.context.get_messages()
                        continue
                    response = turn_result.response
                    break

                # Escalate degradation when stream recovery exhausted
                if self._degradation_level < 2:
                    self._degradation_level += 1
                    yield self._emit(
                        LLMResponse(
                            content=f"Degradation escalated to level {self._degradation_level} after stream recovery exhaustion.",
                            model="system",
                            event_type="degraded",
                            metadata={"degradation_level": self._degradation_level},
                        )
                    )
                stream_recoveries = 0
                response = turn_result.response
                break

            if response is None:
                # API timeout: try asking user to rephrase if agent
                if not self.is_subagent:
                    yield self._emit(
                        LLMResponse(
                            content="API returned no response. Trying to continue with reduced context.",
                            model="system",
                            event_type="degraded",
                            metadata={"degradation": "api_timeout"},
                        )
                    )
                break

            response = merge_tool_calls(response)
            if response.tool_calls:
                response = response.model_copy(update={"tool_calls": ensure_tool_call_ids(response.tool_calls)})
            global_cache_metrics().record(response.usage)
            usage_event = self._usage_event(
                response.usage,
                last_prefix_shape if have_last_prefix_shape else None,
                cur_prefix_shape,
            )
            if usage_event is not None:
                yield self._emit(usage_event)
            last_prefix_shape = cur_prefix_shape
            have_last_prefix_shape = True
            if hasattr(self.context, "record_prompt_tokens"):
                self.context.record_prompt_tokens(response.usage)

                # Three-tier compaction strategy (Reasonix parity):
                # 1. soft_compact_ratio (0.5) -> one-time notice
                # 2. compact_ratio (0.8) -> normal compaction
                # 3. compact_force_ratio (0.9) -> forced compaction

                prompt_tokens = getattr(self.context, "last_prompt_tokens", 0)
                compactor = self.context.compactor

                async def _emit_compaction(trigger: str, force: bool = False) -> None:
                    yield self._emit(LLMResponse(
                        content=json.dumps({"trigger": trigger, "prompt_tokens": prompt_tokens}),
                        model="system",
                        event_type="compaction_started",
                    ))
                    info = await self.context.compact_async(force=force)
                    yield self._emit(LLMResponse(
                        content=json.dumps(info),
                        model="system",
                        event_type="compaction_done",
                    ))

                if hasattr(self.context, "compact_async") and compactor.should_force_compact(prompt_tokens):
                    async for evt in _emit_compaction("force", force=True):
                        yield evt
                elif hasattr(self.context, "compact_async") and compactor.should_compact(prompt_tokens):
                    async for evt in _emit_compaction("auto"):
                        yield evt
                elif hasattr(self.context, "_soft_notice_emitted") and compactor.should_soft_compact(prompt_tokens):
                    if not self.context._soft_notice_emitted:
                        self.context._soft_notice_emitted = True
                        notice = (
                            f"[soft-compact] Context usage at {prompt_tokens:,} tokens. "
                            f"Consider wrapping up or the system will auto-compact soon."
                        )
                        yield self._emit(LLMResponse(content=notice, model="system", event_type="notice"))

            raw_tool_calls: str | None = None
            tool_call_payload: list[dict[str, Any]] | None = None
            if response.tool_calls:
                tool_call_payload = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": stable_json_dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
                raw_tool_calls = stable_tool_calls_json(tool_call_payload)

            self.context.add_assistant_message(
                content=response.content,
                tool_calls=tool_call_payload,
                raw_tool_calls=raw_tool_calls,
                reasoning_content=getattr(response, "reasoning_content", None),
            )

            yield self._emit(
                LLMResponse(
                    content=response.content,
                    tool_calls=response.tool_calls,
                    model=response.model,
                    usage=response.usage,
                    event_type="assistant",
                )
            )

            finish_notice = finish_reason_notice(response.usage)
            if finish_notice:
                yield self._emit(LLMResponse(content=finish_notice, model="system", event_type="notice"))

            if not response.tool_calls:
                if (
                    self._handoff_active
                    and not self._used_any_tool
                    and self._handoff_nudges < MAX_EXECUTOR_HANDOFF_NUDGES
                    and response.content
                ):
                    self._handoff_nudges += 1
                    notice = (
                        "[executor-handoff] You are in the executor phase. Use your available tools now "
                        "to carry out the task instead of only restating the plan."
                    )
                    self.context.add_context_block(notice)
                    yield self._emit(LLMResponse(content=notice, model="system", event_type="notice"))
                    continue
                if not self.is_subagent and not has_visible_final_answer(response.content):
                    finish = "unknown"
                    if response.usage:
                        finish = str(response.usage.get("finish_reason", finish))
                    self._empty_final_blocks += 1
                    if self._empty_final_blocks >= MAX_EMPTY_FINAL_BLOCKS:
                        # Graceful degradation: downgrade from agent to ask mode
                        if self.agent_mode == "agent" and not self._mode_downgraded:
                            self._mode_downgraded = True
                            self.agent_mode = "ask"
                            self._empty_final_blocks = 0
                            downgrade_msg = (
                                "[mode-downgraded] Agent loop returned empty responses consecutively. "
                                "Downgraded to ask mode. You can still read files and search code."
                            )
                            self.context.add_context_block(downgrade_msg)
                            yield self._emit(
                                LLMResponse(
                                    content=downgrade_msg,
                                    model="system",
                                    event_type="mode_downgraded",
                                    metadata={"from_mode": "agent", "to_mode": "ask"},
                                )
                            )
                            continue
                        yield self._emit(
                            LLMResponse(
                                content=(
                                    f"Model finished without a visible final answer {self._empty_final_blocks} times."
                                ),
                                model="system",
                                event_type="error",
                            )
                        )
                        break
                    notice = empty_final_notice(
                        response.model,
                        finish_reason=finish,
                        reasoning_len=len(response.content or ""),
                    )
                    self.context.add_context_block(empty_final_retry_message())
                    yield self._emit(LLMResponse(content=notice, model="system", event_type="notice"))
                    continue
                if response.content and not self.is_subagent:
                    readiness = final_readiness_check(
                        self.evidence,
                        plan_mode_active=self.plan_state.active,
                        project_checks=self.project_checks,
                        external_todos=self.tools.todo.current(),
                    )
                    if readiness.blocked and self._final_readiness_blocks < 3:
                        self._final_readiness_blocks += 1
                        notice = (
                            f"[final-readiness] Cannot finish yet: {readiness.reason}. "
                            "Complete remaining todos or run verification commands, then try again."
                        )
                        self.context.add_context_block(notice)
                        yield self._emit(LLMResponse(content=notice, model="system", event_type="notice"))
                        continue
                # Smart termination: detect "all done" loops
                self._no_tool_turns += 1
                content_lower = (response.content or "").lower().strip()
                done_phrases = {"all done", "done", "finished", "completed", "that's all", "all finished"}
                if content_lower in done_phrases or (
                    len(content_lower) < 20 and any(content_lower.startswith(p) for p in done_phrases)
                ):
                    self._all_done_counter += 1
                    if self._all_done_counter >= 3:
                        yield self._emit(
                            LLMResponse(
                                content="Smart termination: model repeated 'done' without tool calls 3 times.",
                                model="system",
                                event_type="notice",
                            )
                        )
                        break
                else:
                    self._all_done_counter = 0

                # Consecutive turns without tool calls
                if self._no_tool_turns >= 3:
                    yield self._emit(
                        LLMResponse(
                            content=f"Smart termination: {self._no_tool_turns} consecutive turns without tool calls.",
                            model="system",
                            event_type="notice",
                        )
                    )
                    break

                # GoalState integration
                if self.goal_state and not self.is_subagent:
                    follow_up = self.goal_state.parse_response(response.content or "")
                    if not follow_up and self._used_any_tool:
                        yield self._emit(
                            LLMResponse(
                                content="GoalState satisfied. Finishing loop.",
                                model="system",
                                event_type="notice",
                            )
                        )
                        break

                # Check if evidence ledger shows all steps complete
                if self.evidence and not self.is_subagent:
                    pending = self.evidence.pending_steps()
                    if not pending and self._used_any_tool:
                        yield self._emit(
                            LLMResponse(
                                content="All evidence steps completed. Finishing loop.",
                                model="system",
                                event_type="notice",
                            )
                        )
                        break
                break

            self._empty_final_blocks = 0
            self._no_tool_turns = 0
            self._used_any_tool = True
            self._turn_outcomes = []

            for tool_call in response.tool_calls:
                yield self._emit_tool_dispatch(tool_call, partial=False, model=response.model)

            # Batch consecutive read-only tools in parallel
            batch: list[Any] = []
            for tool_call in response.tool_calls:
                if self.tools.is_read_only(tool_call.name):
                    batch.append(tool_call)
                else:
                    if batch:
                        executed = await execute_tool_calls_parallel(self.tools, batch)
                        for tc, res in executed:
                            async for resp in self._handle_tool_call(tc, prefetched_result=res):
                                yield resp
                        batch = []
                    async for resp in self._handle_tool_call(tool_call):
                        yield resp
            if batch:
                executed = await execute_tool_calls_parallel(self.tools, batch)
                for tc, res in executed:
                    async for resp in self._handle_tool_call(tc, prefetched_result=res):
                        yield resp
            storm = self.storm_breaker.apply_turn(self._turn_outcomes)
            if storm is not None:
                tool_call_id, new_output, notice = storm
                self.context.update_tool_result(tool_call_id, new_output)
                self._turn_outcomes[0].output = new_output
                yield self._emit(LLMResponse(content=notice, model="system", event_type="notice"))
            # Circuit breaker: advance iteration
            self.circuit_breaker.next_iteration()
            
            # Watchdog: periodic check (15s interval) with 5min timeout
            now = time.time()
            elapsed = now - self._start_time
            idle_time = now - self._last_activity_time

            # 5-minute absolute timeout
            if elapsed > 300 and self._used_any_tool:
                yield self._emit(
                    LLMResponse(
                        content="[watchdog] Total execution time exceeded 5 minute timeout. Forcing termination.",
                        model="system",
                        event_type="watchdog_timeout",
                        metadata={
                            "elapsed_s": round(elapsed, 1),
                            "idle_s": round(idle_time, 1),
                            "action": "timeout_termination",
                        },
                    )
                )
                hit_max_iterations = True
                break

            # Idle detection
            if idle_time > 15 and self._used_any_tool:
                if not self._watchdog_fired:
                    self._watchdog_fired = True
                    yield self._emit(
                        LLMResponse(
                            content=f"[watchdog] Idle for {idle_time:.0f}s. Checking if stuck.",
                            model="system",
                            event_type="watchdog_check",
                            metadata={
                                "elapsed_s": round(elapsed, 1),
                                "idle_s": round(idle_time, 1),
                                "action": "idle_check",
                            },
                        )
                    )
                if idle_time > 60:
                    yield self._emit(
                        LLMResponse(
                            content="[watchdog] Extended idle detected. Attempting to re-engage the model.",
                            model="system",
                            event_type="watchdog_idle",
                            metadata={
                                "elapsed_s": round(elapsed, 1),
                                "idle_s": round(idle_time, 1),
                                "action": "idle_nudge",
                            },
                        )
                    )
                    self._last_activity_time = now
                    self._watchdog_fired = False
            else:
                self._watchdog_fired = False
            self._last_activity_time = now

            # Prefetch: build context cache for next iteration while idle
            self.context.get_messages()
            iteration += 1
        if hit_max_iterations:
            yield self._emit(
                LLMResponse(
                    content="Maximum number of iterations reached. Stopping to avoid infinite loop.",
                    model="system",
                    event_type="error",
                )
            )
        if self._plan_exec_window:
            self.plan_state.execution_window_active = False

    def _last_assistant_text(self) -> str:
        for msg in reversed(self.context.messages):
            if getattr(msg.role, "value", str(msg.role)) == "assistant" and msg.content:
                return str(msg.content)
        return ""

    async def _run_goal_continuations(self) -> AsyncIterator[LLMResponse]:
        while True:
            follow_up = self.goal_state.parse_response(self._last_assistant_text())
            if not follow_up:
                break
            async for resp in self._run_inner(follow_up):
                yield resp

    async def _handle_tool_call(
        self,
        tool_call: Any,
        prefetched_result: str | None = None,
    ) -> AsyncIterator[LLMResponse]:
        if self.plan_state.active:
            block = plan_mode_block_reason(tool_call.name, tool_call.arguments)
            if block:
                result = plan_mode_tool_result(tool_call.name, block)
                self._turn_outcomes.append(
                    classify_turn_outcome(
                        tool_call.id,
                        tool_call.name,
                        result,
                        blocked=True,
                        loop_guard=self.loop_guard,
                    )
                )
                self.context.add_tool_result(tool_call_id=tool_call.id, content=result)
                yield self._emit(LLMResponse(content=result, model="tool-result", event_type="tool_result"))
                return

        # Agent mode: ask mode only allows read-only tools
        if self.agent_mode == "ask" and not self.tools.is_read_only(tool_call.name):
            result = json.dumps({
                "error": f"Tool '{tool_call.name}' is not allowed in ask mode. Only read-only tools are permitted."
            })
            self._turn_outcomes.append(
                classify_turn_outcome(
                    tool_call.id,
                    tool_call.name,
                    result,
                    blocked=True,
                    loop_guard=self.loop_guard,
                )
            )
            self.context.add_tool_result(tool_call_id=tool_call.id, content=result)
            yield self._emit(
                LLMResponse(
                    content=f"Tool '{tool_call.name}' blocked: ask mode only allows read-only operations.",
                    model="permission",
                    event_type="permission",
                )
            )
            return

        # Circuit breaker: check if tool is tripped
        if self.circuit_breaker.is_tripped(tool_call.name):
            result = json.dumps({
                "error": self.circuit_breaker.trip_message(tool_call.name),
                "circuit_breaker": True
            })
            self.context.add_tool_result(tool_call_id=tool_call.id, content=result)
            yield self._emit(
                LLMResponse(
                    content=result,
                    model="tool-result",
                    event_type="tool_result",
                    metadata={"tool_call_id": tool_call.id, "circuit_breaker": True},
                )
            )
            return

        # Manual mode: emit suggested_command for each tool call
        if self.agent_mode == "manual" and tool_call.name not in ("ask", "complete_step", "todo_write"):
            yield self._emit(
                LLMResponse(
                    content=json.dumps({
                        "tool_name": tool_call.name,
                        "arguments": tool_call.arguments,
                        "mode": "manual",
                    }),
                    model="system",
                    event_type="suggested_command",
                    metadata={
                        "tool_name": tool_call.name,
                        "arguments": stable_json_dumps(tool_call.arguments),
                        "mode": "manual",
                        "non_blocking": True,
                    },
                )
            )
            # Non-blocking wait for manual approval (max 5 minutes)
            if self.pending_permissions or self.pending_asks:
                # Yield control back while waiting for approval
                yield self._emit(
                    LLMResponse(
                        content="",
                        model="system",
                        event_type="waiting_for_approval",
                        metadata={"tool_name": tool_call.name, "mode": "manual"},
                    )
                )

        if tool_call.name == "ask":
            async for resp in self._handle_ask_tool(tool_call):
                yield resp
            return

        pre_hook = await fire_hooks(
            "PreToolUse",
            self.tools.working_dir,
            {"tool": tool_call.name, "args": stable_json_dumps(tool_call.arguments)},
        )
        if pre_hook:
            self.context.add_context_block(pre_hook)

        checkpoint_paths = CheckpointManager.paths_for_tool(tool_call.name, tool_call.arguments)
        if checkpoint_paths:
            checkpoint = self.checkpoints.snapshot(checkpoint_paths, label=tool_call.name)
            if checkpoint is not None:
                yield self._emit(
                    LLMResponse(
                        content=json.dumps(
                            {
                                "checkpoint_id": checkpoint.id,
                                "label": checkpoint.label,
                                "files": checkpoint_paths,
                            }
                        ),
                        model="checkpoint",
                        event_type="checkpoint",
                    )
                )

        decision = self.permission_evaluator.evaluate(
            tool_call.name,
            tool_call.arguments,
            plan_execution_window=self._plan_exec_window,
        )
        result: str
        blocked = False
        if not decision.allowed:
            result = json.dumps({"error": f"Permission denied: {decision.reason}"})
            blocked = True
            yield self._emit(
                LLMResponse(
                    content=f"Permission denied for {tool_call.name}: {decision.reason}",
                    model="permission",
                    event_type="permission",
                )
            )
        else:
            block_msg = self.repeat_guard.should_block(tool_call.name, tool_call.arguments)
            if block_msg:
                result = json.dumps({"error": block_msg})
                self.evidence.record(
                    tool_call.name,
                    tool_call.arguments,
                    success=False,
                    read_only=self.tools.is_read_only(tool_call.name),
                )
                self._turn_outcomes.append(
                    classify_turn_outcome(
                        tool_call.id,
                        tool_call.name,
                        result,
                        blocked=True,
                        loop_guard=self.loop_guard,
                    )
                )
                self.context.add_tool_result(tool_call_id=tool_call.id, content=result)
                yield self._emit(LLMResponse(content=result, model="tool-result", event_type="tool_result"))
                return

            # Emit tool_executing event before execution (real-time status for frontend)
            import time
            yield self._emit(
                LLMResponse(
                    content="",
                    model="system",
                    event_type="tool_executing",
                    metadata={
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.name,
                        "arguments": stable_json_dumps(tool_call.arguments),
                        "started_at": time.time(),
                    },
                )
            )

            if prefetched_result is not None and decision.execution_mode == ExecutionMode.LOCAL:
                result = prefetched_result
            elif decision.execution_mode == ExecutionMode.PROMPT:
                request_id = str(uuid.uuid4())
                future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
                self.pending_permissions[request_id] = future
                yield self._emit(
                    LLMResponse(
                        content=json.dumps(
                            {
                                "request_id": request_id,
                                "tool": tool_call.name,
                                "arguments": tool_call.arguments,
                                "reason": decision.reason,
                            }
                        ),
                        model="permission",
                        event_type="permission",
                    )
                )
                approved = await future
                self.pending_permissions.pop(request_id, None)
                if not approved:
                    result = json.dumps({"error": "User denied permission"})
                    blocked = True
                else:
                    self.permission_evaluator.grant_session(
                        tool_call.name,
                        tool_call.arguments,
                        scope=self._pending_grant_scope,
                    )
                    self._pending_grant_scope = "once"
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    result = self._tag_result(result, "prompt-approved")
            elif decision.execution_mode == ExecutionMode.SANDBOX:
                result = await self._execute_in_sandbox(tool_call.name, tool_call.arguments)
                result = self._tag_result(result, "sandbox")
            else:
                result = (
                    prefetched_result
                    if prefetched_result is not None
                    else await self.tools.execute(tool_call.name, tool_call.arguments)
                )

        result, trunc_notice = limit_tool_output(result)
        if trunc_notice:
            yield self._emit(LLMResponse(content=trunc_notice, model="system", event_type="notice"))
        success = not self.loop_guard.is_error_result(result)
        step = ""
        if tool_call.name == "complete_step" and success:
            try:
                payload = json.loads(result)
                if payload.get("accepted"):
                    step = str(tool_call.arguments.get("step", ""))
            except json.JSONDecodeError:
                pass
        self.evidence.record(
            tool_call.name,
            tool_call.arguments,
            success=success,
            read_only=self.tools.is_read_only(tool_call.name),
            step=step,
        )
        self.circuit_breaker.record(tool_call.name, success)
        if success:
            self.repeat_guard.record_success(tool_call.name, tool_call.arguments)

        if not success:
            err = self.loop_guard.extract_error(result)
            if self.loop_guard.record_failure(tool_call.name, tool_call.arguments, err):
                result = self.loop_guard.guard_message(tool_call.name, tool_call.arguments, err)
                yield self._emit(LLMResponse(content=result[:500], model="system", event_type="notice"))
        else:
            self.loop_guard.record_success(tool_call.name, tool_call.arguments)

        self._turn_outcomes.append(
            classify_turn_outcome(
                tool_call.id,
                tool_call.name,
                result,
                blocked=blocked,
                loop_guard=self.loop_guard,
            )
        )

        self.context.add_tool_result(tool_call_id=tool_call.id, content=result)
        await fire_hooks("PostToolUse", self.tools.working_dir, {"tool": tool_call.name, "result": result[:500]})
        yield self._emit(
            LLMResponse(
                content=result,
                tool_calls=[],
                model="tool-result",
                event_type="tool_result",
                metadata={"tool_call_id": tool_call.id},
            )
        )

    async def respond_permission(self, request_id: str, approved: bool, grant_scope: str = "once") -> bool:
        future = self.pending_permissions.get(request_id)
        if future is None or future.done():
            return False
        self._pending_grant_scope = grant_scope if approved else "once"
        future.set_result(approved)
        return True

    async def wait_for_ask(self, request_id: str, questions: list[dict[str, Any]]) -> str:
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self.pending_asks[request_id] = future
        return await future

    async def respond_ask(self, request_id: str, answers: list[dict[str, Any]]) -> bool:
        future = self.pending_asks.get(request_id)
        if future is None or future.done():
            return False
        result = self.ask_handler.respond(request_id, answers)
        if result is None:
            future.set_result(self.ask_handler.headless_fallback([]))
        else:
            future.set_result(result)
        return True

    def list_pending_asks(self) -> list[dict[str, Any]]:
        return [{"request_id": rid} for rid in self.pending_asks if not self.pending_asks[rid].done()]

    async def _handle_ask_tool(self, tool_call: Any) -> AsyncIterator[LLMResponse]:
        questions = tool_call.arguments.get("questions", [])
        request_id = uuid.uuid4().hex[:12]
        payload = json.dumps({"request_id": request_id, "questions": questions})
        yield self._emit(
            LLMResponse(content=payload, model="ask", event_type="ask", metadata={"request_id": request_id})
        )
        if self.interactive_ask:
            try:
                result = await self.wait_for_ask(request_id, questions)
            except asyncio.CancelledError:
                result = self.ask_handler.headless_fallback(questions)
        else:
            result = self.ask_handler.headless_fallback(questions)
        self.pending_asks.pop(request_id, None)
        self.context.add_tool_result(tool_call_id=tool_call.id, content=result)
        yield self._emit(
            LLMResponse(
                content=result,
                model="tool-result",
                event_type="tool_result",
                metadata={"tool_call_id": tool_call.id},
            )
        )

    def list_pending_permissions(self) -> list[dict[str, Any]]:
        return [{"request_id": rid} for rid in self.pending_permissions if not self.pending_permissions[rid].done()]

    def rewind(self, checkpoint_id: str | None = None) -> dict[str, Any]:
        return self.checkpoints.rewind(checkpoint_id)

    def list_checkpoints(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.checkpoints.list_checkpoints()]

    async def run_stream(self, prompt: str) -> AsyncIterator[LLMResponse]:
        async for chunk in self.run(prompt):
            yield chunk

    async def _execute_in_sandbox(self, tool_name: str, arguments: dict[str, Any]) -> str:
        from likecodex_engine.permissions.classifier import RiskClassifier, RiskLevel

        require_sandbox = self.permission_evaluator.mode == ApprovalMode.SANDBOX_REQUIRED
        if tool_name == "run_command":
            command = arguments.get("command", "")
            high_risk = RiskClassifier.classify_command(str(command)) == RiskLevel.HIGH
            no_fallback = require_sandbox or high_risk
            payload = {"command": command, "working_dir": str(self.tools.working_dir)}
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(self.sandbox_executor_url, json=payload) as resp,
                ):
                    body = await resp.json()
                    if resp.status >= 400 or "error" in body:
                        err = body.get("error", f"sandbox HTTP {resp.status}")
                        if no_fallback:
                            return json.dumps({"error": f"Sandbox execution failed: {err}"})
                        tagged = await self.tools.execute(tool_name, arguments)
                        self._sandbox_fallbacks += 1
                        if self._sandbox_fallbacks >= 3 and self._degradation_level < 2:
                            self._degradation_level += 1
                        yield self._emit(
                            LLMResponse(
                                content=f"Sandbox unavailable, falling back to local execution: {err}",
                                model="system",
                                event_type="degraded",
                                metadata={"sandbox_fallbacks": self._sandbox_fallbacks},
                            )
                        )
                        return self._tag_result(tagged, "fallback-local")
                    return json.dumps(body)
            except Exception as exc:
                if no_fallback:
                    return json.dumps({"error": f"Sandbox unreachable: {exc}"})
                tagged = await self.tools.execute(tool_name, arguments)
                yield self._emit(
                    LLMResponse(
                        content=f"Sandbox unreachable, falling back to local execution: {exc}",
                        model="system",
                        event_type="degraded",
                    )
                )
                return self._tag_result(tagged, "fallback-local")
        if require_sandbox:
            return json.dumps({"error": f"Tool {tool_name} must run in sandbox but only run_command is supported"})
        raw = await self.tools.execute(tool_name, arguments)
        return self._tag_result(raw, "sandbox")

    @staticmethod
    def _tag_result(raw_result: str, tag: str) -> str:
        try:
            data: dict[str, Any] = json.loads(raw_result)
        except Exception:
            data = {"output": raw_result}
        data["execution_tag"] = tag
        return json.dumps(data)

    def _capture_prefix_shape(self, tool_schemas: list[dict[str, Any]]) -> PrefixShape:
        if hasattr(self.context, "capture_prefix_shape"):
            return self.context.capture_prefix_shape(tool_schemas)
        system = self.context.messages[0].content if self.context.messages else ""
        from likecodex_engine.context.cache_shape import capture_prefix_shape

        rewrite_version = int(getattr(self.context, "rewrite_version", 0))
        return capture_prefix_shape(system, tool_schemas, rewrite_version)

    def _usage_event(
        self,
        usage: dict[str, Any] | None,
        previous: PrefixShape | None,
        current: PrefixShape,
    ) -> LLMResponse | None:
        if not usage or int(usage.get("total_tokens", 0)) <= 0:
            return None
        diagnostics = compare_prefix_shape(previous, current, usage)
        line = format_usage_line(usage, diagnostics)
        if not line:
            return None
        source = "subagent" if self.is_subagent else "executor"
        return LLMResponse(
            content=line,
            model="system",
            event_type="usage",
            usage=usage,
            metadata={
                "usage_source": source,
                "cache_diagnostics": diagnostics.to_dict(),
            },
        )

    def _emit(self, response: LLMResponse) -> LLMResponse:
        if self.on_event:
            self.on_event(response)
        return response

    def _emit_tool_dispatch(self, tool_call: Any, *, partial: bool, model: str = "") -> LLMResponse:
        return self._emit(
            LLMResponse(
                content="",
                model=model,
                event_type="tool_dispatch",
                metadata={
                    "tool_name": tool_call.name,
                    "tool_call_id": tool_call.id,
                    "partial": partial,
                    "arguments": {} if partial else tool_call.arguments,
                    "read_only": self.tools.is_read_only(tool_call.name),
                },
            )
        )

    @staticmethod
    def _dependencies_met(step: PlanStep, steps: list[PlanStep]) -> bool:
        completed = {s.id for s in steps if s.status == StepStatus.COMPLETED}
        return all(dep in completed for dep in step.depends_on)

    @staticmethod
    def _parallelizable_steps(steps: list[PlanStep]) -> list[PlanStep]:
        if len(steps) < 2:
            return []
        roots = [s for s in steps if not s.depends_on]
        return roots if len(roots) > 1 else []

    def _summarize_conversation(self) -> str:
        parts: list[str] = []
        for message in self.context.messages[-6:]:
            if message.role.value in {"user", "assistant"} and message.content:
                parts.append(f"{message.role.value}: {message.content[:200]}")
        return "\n".join(parts)


def build_subagent_loop(
    parent: AgentLoop,
    tool_whitelist: list[str] | None,
    max_steps: int | None,
) -> AgentLoop:
    """Factory helper for sub-agents with isolated context and filtered tools."""
    sub_tools = subagent_tool_registry(parent.tools, tool_whitelist)
    sub_context = ContextManager()
    if hasattr(sub_context, "set_working_dir"):
        sub_context.set_working_dir(parent.tools.working_dir)
    steps = max_steps or max(10, parent.max_iterations // 2)
    return AgentLoop(
        llm=parent.llm,
        tools=sub_tools,
        context=sub_context,
        max_iterations=steps,
        permission_evaluator=parent.permission_evaluator,
        sandbox_executor_url=parent.sandbox_executor_url,
        session_id=f"{parent.session_id or 'sub'}-sub",
        checkpoints=CheckpointManager(parent.tools.working_dir),
        is_subagent=True,
    )
