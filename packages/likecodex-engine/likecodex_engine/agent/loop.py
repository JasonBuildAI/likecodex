"""Core agentic loop for LikeCodex."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import aiohttp

from likecodex_engine.agent.planner import Plan, Planner, PlanStep, StepStatus
from likecodex_engine.context.manager import ContextManager, stable_json_dumps, stable_tool_calls_json
from likecodex_engine.llm.base import LLMProvider, LLMResponse
from likecodex_engine.llm.cache_metrics import global_cache_metrics
from likecodex_engine.memory.vector import VectorMemory
from likecodex_engine.permissions.classifier import RiskClassifier, RiskLevel
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
        agent_factory: Callable[[], AgentLoop] | None = None,
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
        self.pending_permissions: dict[str, asyncio.Future[bool]] = {}

    async def run(self, prompt: str) -> AsyncIterator[LLMResponse]:
        """Execute the loop for a single user prompt."""
        if self.memory:
            memories = self.memory.search(prompt, top_k=3)
            if memories:
                snippet = "\n".join(f"- {m.get('text', '')}" for m in memories)
                self.context.add_context_block(f"Relevant memory:\n{snippet}")

        self.context.add_user_message(prompt)

        plan: Plan | None = None
        if self.planner:
            plan = await self.planner.plan(self.session_id or "task", prompt)
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

        tool_schemas = self.tools.to_openai_schema()

        for _iteration in range(self.max_iterations):
            messages = self.context.get_messages()
            response = await self.llm.complete(
                messages,
                tools=tool_schemas if tool_schemas else None,
                temperature=0.0,
                max_tokens=4096,
            )
            global_cache_metrics().record(response.usage)

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

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                async for resp in self._handle_tool_call(tool_call):
                    yield resp
        else:
            yield self._emit(
                LLMResponse(
                    content="Maximum number of iterations reached. Stopping to avoid infinite loop.",
                    model="system",
                    event_type="error",
                )
            )

    async def _handle_tool_call(self, tool_call: Any) -> AsyncIterator[LLMResponse]:
        decision = self.permission_evaluator.evaluate(tool_call.name, tool_call.arguments)
        result: str
        if not decision.allowed:
            result = json.dumps({"error": f"Permission denied: {decision.reason}"})
            yield self._emit(
                LLMResponse(
                    content=f"Permission denied for {tool_call.name}: {decision.reason}",
                    model="permission",
                    event_type="permission",
                )
            )
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
                yield self._emit(
                    LLMResponse(
                        content=f"User denied {tool_call.name}",
                        model="permission",
                        event_type="permission",
                    )
                )
            else:
                raw_result = await self.tools.execute(tool_call.name, tool_call.arguments)
                result = self._tag_result(raw_result, "prompt-approved")
                yield self._emit(
                    LLMResponse(
                        content=f"Approved and executed {tool_call.name}",
                        model="permission",
                        event_type="permission",
                    )
                )
        elif decision.execution_mode == ExecutionMode.SANDBOX:
            raw_result = await self._execute_in_sandbox(tool_call.name, tool_call.arguments)
            result = self._tag_result(raw_result, "sandbox")
            yield self._emit(
                LLMResponse(
                    content=f"High-risk tool {tool_call.name} executed in sandbox mode.",
                    model="permission",
                    event_type="permission",
                )
            )
        else:
            result = await self.tools.execute(tool_call.name, tool_call.arguments)

        self.context.add_tool_result(tool_call_id=tool_call.id, content=result)
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

    async def run_stream(self, prompt: str) -> AsyncIterator[LLMResponse]:
        async for chunk in self.run(prompt):
            yield chunk

    async def _execute_in_sandbox(self, tool_name: str, arguments: dict[str, Any]) -> str:
        require_sandbox = self.permission_evaluator.mode == ApprovalMode.SANDBOX_REQUIRED
        if tool_name == "run_command":
            command = arguments.get("command", "")
            high_risk = RiskClassifier.classify_command(str(command)) == RiskLevel.HIGH
            no_fallback = require_sandbox or high_risk
            payload = {
                "command": command,
                "working_dir": str(self.tools.working_dir),
            }
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

    def _emit(self, response: LLMResponse) -> LLMResponse:
        if self.on_event:
            self.on_event(response)
        return response

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
