"""Simple task planner for complex coding tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from likecodex_engine.llm.base import LLMProvider, Message, Role


class StepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    id: str
    description: str
    status: StepStatus = StepStatus.PENDING
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Plan:
    task_id: str
    reasoning: str
    steps: list[PlanStep] = field(default_factory=list)


class Planner:
    """Breaks a user request into ordered steps."""

    SYSTEM_PROMPT = """You are a senior engineering planner.
Given a coding task, produce a concise plan as JSON with this structure:
{
  "reasoning": "<why this plan>",
  "steps": [
    {"id": "1", "description": "<step 1>", "depends_on": []},
    {"id": "2", "description": "<step 2>", "depends_on": ["1"]}
  ]
}
Keep steps small, actionable, and limited to at most 10."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def plan(self, task_id: str, prompt: str) -> Plan:
        messages = [
            Message(role=Role.SYSTEM, content=self.SYSTEM_PROMPT),
            Message(role=Role.USER, content=f"Task: {prompt}"),
        ]
        response = await self.llm.complete(messages, temperature=0.0, max_tokens=2048)
        import json

        try:
            data: dict[str, Any] = json.loads(self._extract_json(response.content))
        except json.JSONDecodeError:
            data = {"reasoning": "fallback linear plan", "steps": []}

        steps = [
            PlanStep(
                id=s["id"],
                description=s["description"],
                depends_on=s.get("depends_on", []),
            )
            for s in data.get("steps", [])
        ]
        if not steps:
            steps.append(PlanStep(id="1", description=prompt))
        return Plan(
            task_id=task_id,
            reasoning=data.get("reasoning", ""),
            steps=steps,
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = text[3:]
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip("`\n")
        return text.strip()
