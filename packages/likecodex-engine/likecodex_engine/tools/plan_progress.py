"""Plan-mode step completion with evidence sign-off."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

VALID_EVIDENCE = frozenset({"verification", "diff", "files", "manual"})


class PlanProgressTools:
    def __init__(
        self,
        session_log_provider: Callable[[], list[Any]] | None = None,
        todo_tools: Any | None = None,
    ) -> None:
        self._completed: list[dict[str, Any]] = []
        self._session_log = session_log_provider
        self._todo = todo_tools

    def complete_step_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Record evidence-backed completion of ONE plan step. verification requires "
                "command matching session bash history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "step": {"type": "string", "description": "Step title or id"},
                    "result": {"type": "string", "description": "What is now true"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string", "enum": sorted(VALID_EVIDENCE)},
                                "summary": {"type": "string"},
                                "command": {"type": "string"},
                                "paths": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["kind", "summary"],
                        },
                    },
                    "notes": {"type": "string"},
                },
                "required": ["step", "result", "evidence"],
            },
        }

    def _commands_in_session(self) -> list[str]:
        commands: list[str] = []
        if not self._session_log:
            return commands
        for msg in self._session_log():
            if getattr(msg, "role", None) and msg.role.value == "tool":
                try:
                    data = json.loads(msg.content)
                    if isinstance(data, dict) and data.get("command"):
                        commands.append(str(data["command"]).strip())
                except json.JSONDecodeError:
                    pass
        return commands

    def _verify_command(self, command: str) -> bool:
        cmd = command.strip()
        return any(
            ran == cmd or ran.startswith(cmd) or cmd.startswith(ran)
            for ran in self._commands_in_session()
        )

    async def complete_step(
        self,
        step: str,
        result: str,
        evidence: list[dict[str, Any]],
        notes: str = "",
    ) -> str:
        if not evidence:
            return json.dumps({"accepted": False, "error": "At least one evidence item required"})
        for item in evidence:
            kind = item.get("kind", "")
            if kind not in VALID_EVIDENCE:
                return json.dumps({"accepted": False, "error": f"Invalid evidence kind: {kind!r}"})
            if kind == "verification":
                cmd = item.get("command", "").strip()
                if not cmd:
                    return json.dumps({"accepted": False, "error": "verification evidence requires command"})
                if not self._verify_command(cmd):
                    return json.dumps(
                        {
                            "accepted": False,
                            "error": f"Command not found in session history: {cmd!r}",
                        }
                    )
        record = {
            "step": step,
            "result": result,
            "evidence": evidence,
            "notes": notes,
        }
        self._completed.append(record)
        todo_msg = ""
        if self._todo and hasattr(self._todo, "advance_on_complete"):
            todo_msg = self._todo.advance_on_complete(step)
        kinds = ",".join(e.get("kind", "") for e in evidence)
        return json.dumps(
            {
                "accepted": True,
                "step": step,
                "evidence_kinds": kinds,
                "todo": todo_msg,
                "message": f"Step {step!r} signed off with {len(evidence)} evidence item(s).",
            }
        )

    def completed(self) -> list[dict[str, Any]]:
        return list(self._completed)
