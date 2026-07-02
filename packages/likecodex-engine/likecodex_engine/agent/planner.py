"""Simple task planner for complex coding tasks."""

from __future__ import annotations

import json
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

    async def incremental_replan(
        self,
        current_plan: Plan,
        completed_steps: list[str],
        failed_step: str,
        error_info: str = "",
    ) -> Plan:
        """Incrementally replan after a step failure.

        Preserves completed steps and uses the LLM to replan only the
        failed step and its remaining successors.

        Args:
            current_plan: The original plan that encountered a failure.
            completed_steps: IDs of steps that have already succeeded.
            failed_step: The ID of the step that failed.
            error_info: Optional error description from the failed execution.

        Returns:
            A new Plan with completed steps preserved and remaining steps replanned.
        """
        kept_steps = [s for s in current_plan.steps if s.id in completed_steps]

        remaining_descriptions = [
            s.description
            for s in current_plan.steps
            if s.id not in completed_steps
        ]

        failed_desc = next(
            (s.description for s in current_plan.steps if s.id == failed_step),
            "unknown",
        )

        replan_prompt = (
            f"The original plan for task '{current_plan.task_id}' failed at step "
            f"'{failed_step}'.\n"
            f"Failed step description: {failed_desc}\n"
            f"Error: {error_info}\n\n"
            f"The following steps still need to be completed:\n"
        )
        for i, desc in enumerate(remaining_descriptions, 1):
            replan_prompt += f"{i}. {desc}\n"
        replan_prompt += (
            "\nPlease provide an updated plan for the remaining steps, "
            "taking the failure information into account. "
            "Return JSON with the same format as the original plan."
        )

        messages = [
            Message(role=Role.SYSTEM, content=self.SYSTEM_PROMPT),
            Message(role=Role.USER, content=replan_prompt),
        ]
        response = await self.llm.complete(messages, temperature=0.0, max_tokens=2048)

        try:
            data = json.loads(self._extract_json(response.content))
        except json.JSONDecodeError:
            data = {"reasoning": "fallback replan", "steps": []}

        replanned_steps = [
            PlanStep(
                id=s["id"],
                description=s["description"],
                depends_on=s.get("depends_on", []),
            )
            for s in data.get("steps", [])
        ]
        if not replanned_steps:
            replanned_steps = [
                PlanStep(id=s.id, description=s.description, depends_on=s.depends_on)
                for s in current_plan.steps
                if s.id not in completed_steps
            ]

        merged_steps = kept_steps + replanned_steps
        return Plan(
            task_id=current_plan.task_id,
            reasoning=(
                f"Incremental replan after '{failed_step}' failure: "
                f"{data.get('reasoning', 'fallback')}"
            ),
            steps=merged_steps,
        )

    @staticmethod
    def validate_plan(plan: Plan) -> tuple[bool, list[str]]:
        """Validate a plan for completeness, correctness, and feasibility.

        Checks:
        - All steps have non-empty IDs and descriptions.
        - All step IDs are unique.
        - All ``depends_on`` references point to existing steps.
        - No circular dependencies exist.

        Args:
            plan: The Plan to validate.

        Returns:
            Tuple of (is_valid, list_of_issue_messages).
            An empty list means the plan is valid.
        """
        issues: list[str] = []

        if not plan.steps:
            return False, ["Plan has no steps"]

        step_ids = {s.id for s in plan.steps}

        for step in plan.steps:
            if not step.id or not step.id.strip():
                issues.append(f"Step '{step.description[:40]}' has an empty ID")
            if not step.description or not step.description.strip():
                issues.append(f"Step '{step.id}' has an empty description")

        seen_ids: set[str] = set()
        for step in plan.steps:
            if step.id in seen_ids:
                issues.append(f"Duplicate step ID: '{step.id}'")
            seen_ids.add(step.id)

        for step in plan.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    issues.append(
                        f"Step '{step.id}' depends on non-existent step '{dep_id}'"
                    )

        adjacency: dict[str, list[str]] = {s.id: list(s.depends_on) for s in plan.steps}

        def _has_cycle(node: str, visited: set[str], stack: set[str]) -> bool:
            visited.add(node)
            stack.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if _has_cycle(neighbor, visited, stack):
                        return True
                elif neighbor in stack:
                    issues.append(
                        f"Circular dependency detected involving step '{node}' "
                        f"(back edge to '{neighbor}')"
                    )
                    return True
            stack.discard(node)
            return False

        all_nodes = list(adjacency.keys())
        global_visited: set[str] = set()
        for node in all_nodes:
            if node not in global_visited:
                _has_cycle(node, global_visited, set())

        return len(issues) == 0, issues

    @staticmethod
    def estimate_steps(plan: Plan) -> dict[str, Any]:
        """Estimate time required for each step and the overall plan.

        Uses heuristic rules based on step description length,
        dependency count, and keyword patterns to produce a rough
        time estimate in seconds.

        Args:
            plan: The Plan to estimate.

        Returns:
            A dict with:
            - ``total_seconds``: estimated total time for all steps.
            - ``steps``: list of dicts with per-step estimates.
        """
        step_estimates: list[dict[str, Any]] = []
        total_seconds = 0.0

        for step in plan.steps:
            desc = step.description.lower()
            base = 60.0

            if any(kw in desc for kw in ("test", "testing", "verify", "validate", "assert")):
                base += 30.0
            if any(kw in desc for kw in ("refactor", "redesign", "restructure", "migrate")):
                base += 120.0
            if any(kw in desc for kw in ("deploy", "release", "publish", "package")):
                base += 90.0
            if any(kw in desc for kw in ("research", "investigate", "analyze", "design")):
                base += 120.0
            if any(kw in desc for kw in ("debug", "fix", "repair", "resolve")):
                base += 60.0
            if any(kw in desc for kw in ("document", "comment", "readme", "doc")):
                base += 45.0
            if any(kw in desc for kw in ("install", "setup", "configure", "init")):
                base += 30.0

            if len(step.description) > 100:
                base *= 1.3
            elif len(step.description) > 200:
                base *= 1.6

            dep_count = len(step.depends_on)
            if dep_count >= 3:
                base *= 1.2
            elif dep_count >= 5:
                base *= 1.4

            estimate = round(base, 1)
            step_estimates.append({
                "step_id": step.id,
                "description": step.description,
                "estimated_seconds": estimate,
                "estimated_display": f"{estimate / 60:.1f} min",
            })
            total_seconds += estimate

        return {
            "total_seconds": round(total_seconds, 1),
            "total_display": f"{total_seconds / 60:.1f} min",
            "steps": step_estimates,
        }

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        return text
