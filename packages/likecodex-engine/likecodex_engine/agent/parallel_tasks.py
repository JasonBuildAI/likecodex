"""Parallel sub-agent dispatch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from likecodex_engine.agent.loop import AgentLoop


class ParallelTasksTool:
    def __init__(self, agent_factory: Callable[[list[str] | None, int | None], AgentLoop]) -> None:
        self.agent_factory = agent_factory

    def parallel_tasks_schema(self) -> dict[str, Any]:
        return {
            "description": "Run multiple sub-agents in parallel and collect results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "description": {"type": "string"},
                                "tools": {"type": "array", "items": {"type": "string"}},
                                "max_steps": {"type": "integer"},
                            },
                            "required": ["prompt"],
                        },
                    }
                },
                "required": ["tasks"],
            },
        }

    async def _run_one(self, prompt: str, tools: list[str] | None, max_steps: int | None) -> str:
        agent = self.agent_factory(tools, max_steps)
        parts: list[str] = []
        async for resp in agent.run(prompt):
            if resp.event_type == "assistant" and resp.content:
                parts.append(resp.content)
        return "\n".join(parts).strip() or "(no output)"

    async def parallel_tasks(self, tasks: list[dict[str, Any]]) -> str:
        if len(tasks) < 2:
            return json.dumps({"error": "parallel_tasks requires at least 2 tasks"})

        async def run_index(i: int) -> dict[str, Any]:
            t = tasks[i]
            try:
                result = await self._run_one(t["prompt"], t.get("tools"), t.get("max_steps"))
                return {"index": i, "description": t.get("description", ""), "result": result}
            except Exception as exc:
                return {"index": i, "error": str(exc)}

        results = await asyncio.gather(*(run_index(i) for i in range(len(tasks))))
        return json.dumps({"tasks": list(results)})
