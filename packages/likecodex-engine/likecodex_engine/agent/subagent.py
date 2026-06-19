"""Simple sub-agent orchestration for parallel task decomposition."""

from __future__ import annotations

import asyncio
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

    def __init__(self, factory: Any) -> None:
        self.factory = factory

    async def run_parallel(self, subtasks: list[tuple[str, str]]) -> list[SubAgentResult]:
        """Run a list of (subtask_id, description) pairs in parallel."""
        tasks = [self._run_one(subtask_id, desc) for subtask_id, desc in subtasks]
        return await asyncio.gather(*tasks)

    async def _run_one(self, subtask_id: str, description: str) -> SubAgentResult:
        result = SubAgentResult(subtask_id=subtask_id, description=description)
        try:
            agent: AgentLoop = self.factory(None, None)
            async for resp in agent.run(description):
                result.outputs.append(resp)
        except Exception as e:
            result.success = False
            result.error = str(e)
        return result

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
