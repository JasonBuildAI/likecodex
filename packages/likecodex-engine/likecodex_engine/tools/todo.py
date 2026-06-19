"""A lightweight todo list the agent can maintain during a task."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from likecodex_engine.agent.evidence import EvidenceLedger

_VALID_STATUS = {"pending", "in_progress", "completed", "cancelled"}


class TodoTools:
    """Holds an ordered todo list for the current agent run.

    State lives on the instance (one registry per session), so the model can
    track multi-step work without persisting anything to disk.
    """

    def __init__(self) -> None:
        self._todos: list[dict[str, Any]] = []
        self._ledger: EvidenceLedger | None = None

    def set_evidence_ledger(self, ledger: EvidenceLedger | None) -> None:
        self._ledger = ledger

    def todo_write_schema(self) -> dict[str, Any]:
        return {
            "description": (
                "Create or update the task todo list. Pass the full list each time; "
                "it replaces the previous list. Use for multi-step work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "content": {"type": "string"},
                                "status": {
                                    "type": "string",
                                    "enum": sorted(_VALID_STATUS),
                                },
                            },
                            "required": ["id", "content", "status"],
                        },
                    },
                },
                "required": ["todos"],
            },
        }

    async def todo_write(self, todos: list[dict[str, Any]]) -> str:
        cleaned: list[dict[str, Any]] = []
        for item in todos:
            status = str(item.get("status", "pending"))
            if status not in _VALID_STATUS:
                status = "pending"
            cleaned.append(
                {
                    "id": str(item.get("id", len(cleaned) + 1)),
                    "content": str(item.get("content", "")),
                    "status": status,
                }
            )
        if self._ledger is not None:
            missing = self._ledger.newly_completed_without_receipt(self._todos, cleaned)
            if missing:
                labels = ", ".join(str(m.get("content", m.get("id"))) for m in missing[:3])
                return json.dumps(
                    {
                        "error": (
                            f"{len(missing)} todo(s) newly completed without matching complete_step "
                            f"receipt in this turn ({labels}); sign off with complete_step first"
                        )
                    }
                )
        self._todos = cleaned
        counts = dict.fromkeys(_VALID_STATUS, 0)
        for item in cleaned:
            counts[item["status"]] += 1
        return json.dumps({"todos": cleaned, "summary": counts})

    def current(self) -> list[dict[str, Any]]:
        return list(self._todos)

    def advance_on_complete(self, step: str) -> str:
        """Host-side todo advancement when complete_step accepts."""
        if not self._todos:
            return "no todos"
        step_lower = step.lower()
        matched = False
        for item in self._todos:
            if item["status"] == "in_progress" and (
                step_lower in item["content"].lower() or step_lower in str(item["id"]).lower()
            ):
                item["status"] = "completed"
                matched = True
                break
        if not matched:
            for item in self._todos:
                if item["status"] == "in_progress":
                    item["status"] = "completed"
                    matched = True
                    break
        for item in self._todos:
            if item["status"] == "pending":
                item["status"] = "in_progress"
                return f"advanced: completed step, now in_progress={item['id']}"
        return "advanced: all todos completed" if matched else "no matching in_progress todo"
