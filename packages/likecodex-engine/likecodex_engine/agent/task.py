"""Task tool: spawn an isolated sub-agent."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from likecodex_engine.agent.loop import AgentLoop
    from likecodex_engine.agent.subagent_store import SubagentStore

DEFAULT_TASK_PROMPT = (
    "You are a sub-agent carrying out one focused task. Return a concise, self-contained final answer."
)


class TaskTool:
    def __init__(
        self,
        agent_factory: Callable[[list[str] | None, int | None], AgentLoop],
        store: SubagentStore | None = None,
        parent_session: str | None = None,
        working_dir: str = ".",
    ) -> None:
        self.agent_factory = agent_factory
        self.store = store
        self.parent_session = parent_session or ""
        self.working_dir = working_dir

    def task_schema(self) -> dict[str, Any]:
        return {
            "description": "Spawn a sub-agent to carry out a focused task in isolation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "description": {"type": "string", "description": "Short label"},
                    "tools": {"type": "array", "items": {"type": "string"}},
                    "max_steps": {"type": "integer", "minimum": 1},
                    "continue_from": {
                        "type": "string",
                        "description": "Continue a prior sub-agent transcript by sa_... reference.",
                    },
                    "fork_from": {
                        "type": "string",
                        "description": "Fork a prior sub-agent transcript into a new independent sa_... reference.",
                    },
                },
                "required": ["prompt"],
            },
        }

    async def task(
        self,
        prompt: str,
        description: str = "",
        tools: list[str] | None = None,
        max_steps: int | None = None,
        continue_from: str = "",
        fork_from: str = "",
    ) -> str:
        from likecodex_engine.agent.subagent_store import SubagentRun, SubagentSpec

        if continue_from and fork_from:
            return json.dumps({"error": "continue_from and fork_from are mutually exclusive"})

        spec = SubagentSpec(
            kind="task",
            name=description or prompt[:80],
            parent_session=self.parent_session,
            tool_scope=list(tools or []),
            workspace_root=self.working_dir,
        )

        run: SubagentRun | None = None
        if self.store is not None:
            if continue_from:
                run = self.store.prepare_continue(continue_from, spec)
            elif fork_from:
                run = self.store.prepare_fork(fork_from, spec)
            else:
                run = self.store.prepare_fresh(spec)

        agent = self.agent_factory(tools, max_steps)
        if run and run.messages:
            agent.context._log = list(run.messages)

        parts: list[str] = []
        try:
            async for resp in agent.run(prompt):
                if resp.event_type == "assistant" and resp.content:
                    parts.append(resp.content)
        except Exception as exc:
            if self.store and run:
                self.store.save_failed(run, agent.context.messages)
            elif run:
                run.release()
            return json.dumps({"error": str(exc)})

        answer = "\n".join(parts).strip() or "(no output)"
        payload: dict[str, Any] = {
            "description": description or prompt[:80],
            "result": answer,
        }
        if run and self.store:
            self.store.save_completed(run, agent.context.messages)
            payload["subagent_ref"] = run.ref
            payload["message"] = f"Subagent reference: {run.ref}"
        elif run:
            run.release()
        return json.dumps(payload)
