"""Simple sub-agent orchestration for parallel task decomposition."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from likecodex_engine.agent.loop import AgentLoop

from likecodex_engine.llm.base import LLMResponse


@dataclass
class SubAgentResult:
    subtask_id: str
    description: str
    outputs: list[LLMResponse] = field(default_factory=list)
    success: bool = True
    error: str | None = None


class SubAgentOrchestrator:
    """Runs independent sub-agents in parallel and aggregates results."""

    def __init__(self, factory: Any, on_progress: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.factory = factory
        self.on_progress = on_progress

    async def run_parallel(self, subtasks: list[tuple[str, str]]) -> list[SubAgentResult]:
        """Run a list of (subtask_id, description) pairs in parallel."""
        tasks = [self._run_one(subtask_id, desc) for subtask_id, desc in subtasks]
        return await asyncio.gather(*tasks)

    async def _run_one(self, subtask_id: str, description: str) -> SubAgentResult:
        result = SubAgentResult(subtask_id=subtask_id, description=description)
        self._emit_progress(subtask_id, "started", description)
        try:
            agent: AgentLoop = self.factory(None, None)
            step_count = 0
            async for resp in agent.run(description):
                result.outputs.append(resp)
                step_count += 1
                if step_count % 3 == 0:  # Emit progress every 3 steps
                    self._emit_progress(subtask_id, "running", description, steps=step_count)
            self._emit_progress(subtask_id, "completed", description, steps=step_count)
        except Exception as e:
            result.success = False
            result.error = str(e)
            self._emit_progress(subtask_id, "failed", description, error=str(e))
        return result

    def _emit_progress(self, subtask_id: str, status: str, description: str, steps: int = 0, error: str = "") -> None:
        if self.on_progress:
            self.on_progress({
                "subtask_id": subtask_id,
                "description": description[:100],
                "status": status,
                "steps": steps,
                "error": error,
            })

    @staticmethod
    def summarize(results: list[SubAgentResult]) -> str:
        lines = []
        for r in results:
            status = "OK" if r.success else "FAIL"
            lines.append(f"[{status}] {r.subtask_id}: {r.description}")
            if r.error:
                lines.append(f"  Error: {r.error}")
            for out in r.outputs:
                if out.content:
                    lines.append(f"  - {out.content[:200]}")
        return "\n".join(lines)
