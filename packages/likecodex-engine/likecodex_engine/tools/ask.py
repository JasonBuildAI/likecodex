"""Structured user questions (ask tool)."""

from __future__ import annotations

import json
import uuid
from typing import Any


class AskToolHandler:
    """Handles pending ask requests; wired by AgentLoop."""

    def __init__(self) -> None:
        self.pending: dict[str, dict[str, Any]] = {}

    def create(self, questions: list[dict[str, Any]]) -> tuple[str, str]:
        request_id = uuid.uuid4().hex[:12]
        self.pending[request_id] = {"questions": questions, "answered": False}
        payload = json.dumps({"request_id": request_id, "questions": questions})
        return request_id, payload

    def respond(self, request_id: str, answers: list[dict[str, Any]]) -> str | None:
        entry = self.pending.pop(request_id, None)
        if entry is None:
            return None
        lines = []
        for ans in answers:
            idx = ans.get("questionIndex", ans.get("question_index", 0))
            selected = ans.get("selected", ans.get("choices", []))
            lines.append(f"Q{idx + 1}: {', '.join(selected)}")
        return json.dumps(
            {
                "answers": answers,
                "summary": "User selected: " + "; ".join(lines),
                "headless_note": "",
            }
        )

    def headless_fallback(self, questions: list[dict[str, Any]]) -> str:
        """When no interactive asker is available."""
        assumed = []
        for i, q in enumerate(questions):
            opts = q.get("options") or []
            label = opts[0].get("label", "default") if opts else "default"
            assumed.append(f"Q{i + 1} ({q.get('header', 'choice')}): assumed {label!r} (no user present)")
        return json.dumps(
            {
                "answers": [],
                "summary": " ".join(assumed),
                "headless_note": "Model assumption — no user answered ask tool.",
            }
        )


def ask_tool_schema() -> dict[str, Any]:
    return {
        "description": (
            "Ask the user one or more multiple-choice questions when a decision is genuinely theirs. "
            "YOLO/full-access modes do not auto-answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "header": {"type": "string"},
                            "question": {"type": "string"},
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["label"],
                                },
                            },
                            "multiSelect": {"type": "boolean"},
                        },
                        "required": ["header", "question", "options"],
                    },
                }
            },
            "required": ["questions"],
        },
    }


async def execute_ask(
    handler: AskToolHandler,
    loop: Any,
    questions: list[dict[str, Any]],
) -> str:
    request_id, _ = handler.create(questions)
    if getattr(loop, "interactive_ask", True):
        result = await loop.wait_for_ask(request_id, questions)
        return result or handler.headless_fallback(questions)
    return handler.headless_fallback(questions)
