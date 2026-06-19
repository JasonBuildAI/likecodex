"""Core agentic loop for LikeCodex."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import aiohttp

from likecodex_engine.agent.checkpoints import CheckpointManager
from likecodex_engine.agent.coordinator import EXECUTOR_HANDOFF_MARKER, should_plan
from likecodex_engine.agent.dispatch import execute_tool_calls_parallel
from likecodex_engine.agent.evidence import EvidenceLedger
from likecodex_engine.agent.guards import (
    LoopGuard,
    RepeatSuccessGuard,
    StormBreaker,
    ToolTurnOutcome,
    classify_turn_outcome,
    empty_final_notice,
    empty_final_retry_message,
    finish_reason_notice,
    has_visible_final_answer,
    MAX_EMPTY_FINAL_BLOCKS,
    MAX_EXECUTOR_HANDOFF_NUDGES,
)
from likecodex_engine.agent.output_limit import limit_tool_output
from likecodex_engine.agent.plan_mode import plan_mode_block_reason, plan_mode_tool_result
from likecodex_engine.agent.plan_state import PlanState
from likecodex_engine.agent.planner import Plan, Planner, PlanStep, StepStatus
from likecodex_engine.agent.readiness import final_readiness_check
from likecodex_engine.agent.streaming import (
    MAX_STREAM_RECOVERIES,
    StreamTurnResult,
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
from likecodex_engine.tools.registry import ToolRegistry


class AgentLoop:
    """The canonical loop: model -> tool calls -> results -> repeat."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        context: ContextManager,
        max_iterations: int = 50,
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
        is_subagent: bool = False,
        executor_handoff_guard: bool = False,
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
        self.is_subagent = is_subagent
        self.executor_handoff_guard = executor_handoff_guard
        self._used_any_tool = False
        self._handoff_nudges = 0
        self._handoff_active = False
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
        if self.memory:
            memories = self.memory.search(prompt, top_k=3)
            if memories:
                snippet = "\n".join(f"- {m.get('text', '')}" for m in memories)
                self.context.add_context_block(f"Relevant memory:\n{snippet}")

        self.context.add_user_message(prompt)

        self.evidence.reset()
        self.repeat_guard.reset()
        self.storm_breaker.reset()
        self._turn_outcomes = []
        self._final_readiness_blocks = 0
        self._empty_final_blocks = 0
        self._used_any_tool = False
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

                orchestrator = SubAgentOrchestrator(self.agent_factory)
                results = await orchestrator.run_parallel([(step.id, step.description) for step in parallel])
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

        if self.memory:
            summary = self._summarize_conversation()
            if summary:
                self.memory.add(summary, {"session_id": self.session_id})

    async def _run_inner(self, prompt: str) -> AsyncIterator[LLMResponse]:
        if prompt and self.context.messages[-1].role.value != "user":
            self.context.add_user_message(prompt)

        tool_schemas = [] if self.no_tools else flatten_tool_schemas(self.tools.to_openai_schema())
        stream_recoveries = 0
        last_prefix_shape: PrefixShape | None = None
        have_last_prefix_shape = False

        for _iteration in range(self.max_iterations):
            messages = self.context.get_messages()
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
                                    "reason": "stream_recovery",
                                },
                            )
                        )
                        messages = self.context.get_messages()
                        continue
                    response = turn_result.response
                    break

                stream_recoveries = 0
                response = turn_result.response
                break

            if response is None:
                break

            response = merge_tool_calls(response)
            if response.tool_calls:
                response = response.model_copy(
                    update={"tool_calls": ensure_tool_call_ids(response.tool_calls)}
                )
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
                if hasattr(self.context, "compact_async") and self.context.compactor.should_compact(
                    getattr(self.context, "last_prompt_tokens", 0)
                ):
                    yield self._emit(
                        LLMResponse(
                            content=json.dumps({"trigger": "auto"}),
                            model="system",
                            event_type="compaction_started",
                        )
                    )
                    info = await self.context.compact_async()
                    yield self._emit(
                        LLMResponse(
                            content=json.dumps(info),
                            model="system",
                            event_type="compaction_done",
                        )
                    )

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
                yield self._emit(
                    LLMResponse(content=finish_notice, model="system", event_type="notice")
                )

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
                        yield self._emit(
                            LLMResponse(
                                content=(
                                    f"Model finished without a visible final answer "
                                    f"{self._empty_final_blocks} times."
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
                        yield self._emit(
                            LLMResponse(content=notice, model="system", event_type="notice")
                        )
                        continue
                break

            self._empty_final_blocks = 0
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
                yield self._emit(
                    LLMResponse(content=notice, model="system", event_type="notice")
                )
        else:
            yield self._emit(
                LLMResponse(
                    content="Maximum number of iterations reached. Stopping to avoid infinite loop.",
                    model="system",
                    event_type="error",
                )
            )

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
                yield self._emit(
                    LLMResponse(content=result, model="tool-result", event_type="tool_result")
                )
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

        decision = self.permission_evaluator.evaluate(tool_call.name, tool_call.arguments)
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
                yield self._emit(
                    LLMResponse(content=result, model="tool-result", event_type="tool_result")
                )
                return
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
                    self.permission_evaluator.grant_session(tool_call.name, tool_call.arguments)
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    result = self._tag_result(result, "prompt-approved")
            elif decision.execution_mode == ExecutionMode.SANDBOX:
                result = await self._execute_in_sandbox(tool_call.name, tool_call.arguments)
                result = self._tag_result(result, "sandbox")
            else:
                result = prefetched_result if prefetched_result is not None else await self.tools.execute(
                    tool_call.name, tool_call.arguments
                )

        result, trunc_notice = limit_tool_output(result)
        if trunc_notice:
            yield self._emit(
                LLMResponse(content=trunc_notice, model="system", event_type="notice")
            )
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
        if success:
            self.repeat_guard.record_success(tool_call.name, tool_call.arguments)

        if not success:
            err = self.loop_guard.extract_error(result)
            if self.loop_guard.record_failure(tool_call.name, tool_call.arguments, err):
                result = self.loop_guard.guard_message(tool_call.name, tool_call.arguments, err)
                yield self._emit(
                    LLMResponse(content=result[:500], model="system", event_type="notice")
                )
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

    async def respond_permission(self, request_id: str, approved: bool) -> bool:
        future = self.pending_permissions.get(request_id)
        if future is None or future.done():
            return False
        future.set_result(approved)
        return True

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
                        return self._tag_result(tagged, "fallback-local")
                    return json.dumps(body)
            except Exception as exc:
                if no_fallback:
                    return json.dumps({"error": f"Sandbox unreachable: {exc}"})
                tagged = await self.tools.execute(tool_name, arguments)
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
