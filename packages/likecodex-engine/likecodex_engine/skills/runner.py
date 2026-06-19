"""Skill invocation: inline and subagent modes."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from likecodex_engine.skills.loader import discover_skills

if TYPE_CHECKING:
    from likecodex_engine.agent.loop import AgentLoop


class SkillRunner:
    def __init__(
        self,
        working_dir: str,
        agent_factory: Callable[[list[str] | None, int | None], AgentLoop] | None = None,
    ) -> None:
        self.working_dir = working_dir
        self.agent_factory = agent_factory
        self._skills = {s.name: s for s in discover_skills(working_dir)}

    def reload(self) -> None:
        self._skills = {s.name: s for s in discover_skills(self.working_dir)}

    def run_skill_schema(self) -> dict[str, Any]:
        return {
            "description": "Invoke a skill by name. inline folds body into context; subagent runs isolated loop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "args": {"type": "string", "description": "Optional arguments for the skill"},
                },
                "required": ["name"],
            },
        }

    async def run_skill(self, name: str, args: str = "") -> str:
        self.reload()
        skill = self._skills.get(name)
        if not skill:
            return json.dumps({"error": f"Skill {name!r} not found", "available": sorted(self._skills.keys())})
        body = skill.body
        if args:
            body = body.replace("$ARGS", args).replace("$1", args)
        if skill.run_as == "subagent":
            if not self.agent_factory:
                return json.dumps({"error": "Subagent skills require agent_factory"})
            prompt = f"{skill.description}\n\n{body}"
            if args:
                prompt += f"\n\nArguments: {args}"
            agent = self.agent_factory(None, None)
            parts: list[str] = []
            async for resp in agent.run(prompt):
                if resp.event_type == "assistant" and resp.content:
                    parts.append(resp.content)
            return json.dumps({"skill": name, "mode": "subagent", "result": "\n".join(parts).strip()})
        return json.dumps({"skill": name, "mode": "inline", "body": body[:8000]})

    def skill_index_for_prefix(self) -> str:
        lines = ["Available skills (invoke via run_skill):"]
        for name in sorted(self._skills.keys()):
            s = self._skills[name]
            lines.append(f"- **{name}**: {s.description} (runAs={s.run_as})")
        return "\n".join(lines)
