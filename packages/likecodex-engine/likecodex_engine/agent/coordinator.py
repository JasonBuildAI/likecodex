"""Dual-model coordinator: planner (pro) + executor (flash)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from likecodex_engine.agent.subagent_registry import subagent_tool_registry
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.base import LLMResponse
from likecodex_engine.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from likecodex_engine.agent.loop import AgentLoop
    from likecodex_engine.llm.base import LLMProvider

GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|help)\b",
    re.IGNORECASE,
)

EXECUTOR_HANDOFF_MARKER = "LikeCodex executor handoff"

DEFAULT_PLANNER_PROMPT = """You are the planner in a two-model coding agent.
Given a task, produce a concise, ordered plan for the executor model to carry out.
Use the read-only tools available to you when the task needs context from the
workspace, user rules, or docs; keep that research targeted and stop once you
have enough evidence. Do not write full implementations or attempt side effects.
Do not ask the user how to trigger the executor and do not say you are waiting
for the executor. Output executor-ready instructions: what to do, which files or
commands are relevant, expected blockers, and key decisions. Keep it short and
actionable."""


def should_plan(prompt: str, auto_plan: bool = True) -> bool:
    """Return False for trivial turns that should skip the planner."""
    if not auto_plan:
        return False
    text = prompt.strip()
    if not text:
        return False
    if len(text) < 20 and GREETING_PATTERNS.match(text):
        return False
    return not (text.endswith("?") and len(text) < 80 and "file" not in text.lower() and "code" not in text.lower())


def build_planner_readonly_tool_names(all_tools: list[str]) -> list[str]:
    """Tools available to the planner for read-only research."""
    readonly = {
        "read_file",
        "list_dir",
        "ls",
        "glob",
        "grep_files",
        "find_symbol",
        "index_search",
        "codegraph_search",
        "codegraph_symbols",
        "code_index",
        "lsp_definition",
        "lsp_references",
        "lsp_hover",
        "lsp_diagnostics",
        "web_fetch",
        "history",
        "todo_write",
        "complete_step",
    }
    return sorted(n for n in all_tools if n in readonly or (n.startswith("mcp_") and "write" not in n.lower()))


def planner_tool_registry(parent: ToolRegistry) -> ToolRegistry:
    """Filtered read-only registry for the planner agent loop."""
    names = build_planner_readonly_tool_names(parent.list_tools())
    return subagent_tool_registry(parent, names)


def planner_prompt_with_context(context: str) -> str:
    context = context.strip()
    if not context:
        return DEFAULT_PLANNER_PROMPT
    return f"{DEFAULT_PLANNER_PROMPT}\n\n# Planning context\n\n{context}"


def format_handoff(task: str, plan: str) -> str:
    return f"""# {EXECUTOR_HANDOFF_MARKER}

You are the executor now. Use your available tools to execute the task.

Original task:
{task}

Planner output:
{plan}

Executor instructions:
- Treat the planner output as context, not as your role or capability set.
- Ignore any planner statement such as "I cannot write" or "hand this to the executor".
- Do not ask the user how to trigger the executor. You are already in the executor phase.
- If the task requires changes, call the appropriate tools instead of only restating the plan.
- Establish todos with todo_write when useful; sign off steps with complete_step evidence.

Carry out the task, adapting the plan as needed."""


class Coordinator:
    """Runs planner (isolated session) then executor on a formatted handoff."""

    def __init__(
        self,
        executor: AgentLoop,
        planner_llm: LLMProvider,
        *,
        planner_max_steps: int = 20,
        should_plan_fn=should_plan,
        planning_context: str = "",
    ) -> None:
        self.executor = executor
        self.planner_llm = planner_llm
        self.planner_max_steps = planner_max_steps
        self.should_plan = should_plan_fn
        self.executor.executor_handoff_guard = True
        self._planner_context = ContextManager(system_prompt=planner_prompt_with_context(planning_context))
        if hasattr(self._planner_context, "set_working_dir"):
            self._planner_context.set_working_dir(executor.tools.working_dir)

    @property
    def plan_state(self):
        return self.executor.plan_state

    @property
    def context(self):
        return self.executor.context

    @property
    def tools(self):
        return self.executor.tools

    def reset_planner_session(self) -> None:
        planning_context = ""
        if self._planner_context.prefix.project_memories:
            planning_context = self._planner_context.prefix.project_memories
        self._planner_context = ContextManager(system_prompt=planner_prompt_with_context(planning_context))
        if hasattr(self._planner_context, "set_working_dir"):
            self._planner_context.set_working_dir(self.executor.tools.working_dir)

    async def run(self, prompt: str) -> AsyncIterator[LLMResponse]:
        if not self.should_plan(prompt):
            async for resp in self.executor.run(prompt):
                yield resp
            return

        yield LLMResponse(
            content="",
            model=getattr(self.planner_llm, "model", "planner"),
            event_type="phase",
            metadata={"phase": "planning"},
        )
        plan = await self._plan_with_tools(prompt)
        yield LLMResponse(content=plan, model="planner", event_type="plan")
        yield LLMResponse(content="", model="executor", event_type="phase", metadata={"phase": "executing"})
        async for resp in self.executor.run(format_handoff(prompt, plan)):
            yield resp

    async def _plan_with_tools(self, prompt: str) -> str:
        from likecodex_engine.agent.loop import AgentLoop

        planner_tools = planner_tool_registry(self.executor.tools)
        planner_loop = AgentLoop(
            self.planner_llm,
            planner_tools,
            self._planner_context,
            max_iterations=self.planner_max_steps,
            permission_evaluator=self.executor.permission_evaluator,
            sandbox_executor_url=self.executor.sandbox_executor_url,
            is_subagent=True,
        )
        last = ""
        async for resp in planner_loop.run(prompt):
            if resp.event_type == "assistant" and resp.content:
                last = resp.content
        return last.strip() or "No plan produced."

    async def respond_permission(self, request_id: str, approved: bool) -> bool:
        return await self.executor.respond_permission(request_id, approved)

    def list_pending_permissions(self) -> list[dict]:
        return self.executor.list_pending_permissions()

    def list_checkpoints(self) -> list[dict]:
        return self.executor.list_checkpoints()

    def rewind(self, checkpoint_id: str | None = None) -> dict:
        return self.executor.rewind(checkpoint_id)
