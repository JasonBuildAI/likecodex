"""Auto-plan classifier for borderline tasks."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from likecodex_engine.llm.base import LLMProvider

CLASSIFIER_PROMPT = """You classify whether a coding-agent user request should first enter read-only planning mode.
Return ONLY JSON: {"needs_plan":true|false,"reason":"short reason"}.
Use true for multi-step implementation, refactors, migrations, unclear cross-file work, PRD/spec/issue work, or tasks needing investigation before edits.
Use false for explanations, simple questions, single obvious edits, direct commands, or requests that should be answered without changing files."""


class AutoPlanClassifier:
    """Classifies borderline tasks to determine if planning is needed."""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def needs_plan(self, prompt: str, heuristic_score: int = 0) -> tuple[bool, str]:
        """Determine if the task needs planning.

        Args:
            prompt: User's request
            heuristic_score: Score from heuristic analysis (higher = more likely to need planning)

        Returns:
            Tuple of (needs_plan: bool, reason: str)
        """
        from likecodex_engine.llm.base import Message, Role

        messages = [
            Message(role=Role.SYSTEM, content=CLASSIFIER_PROMPT),
            Message(
                role=Role.USER,
                content=f"heuristic_score={heuristic_score}\n\nUSER_REQUEST:\n{prompt}",
            ),
        ]

        try:
            response = await self.llm.complete(messages, tools=None, temperature=0.0, max_tokens=80)
            content = response.content or ""

            # Extract JSON from response
            json_str = self._extract_json_object(content)
            if not json_str:
                return False, "Failed to parse classifier response"

            data = json.loads(json_str)
            needs_plan = data.get("needs_plan", False)
            reason = data.get("reason", "")

            return bool(needs_plan), str(reason)
        except Exception as e:
            return False, f"Classifier error: {e}"

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Extract JSON object from text."""
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= start:
            return text[start : end + 1]
        return None


def is_borderline_task(prompt: str) -> bool:
    """Heuristic check if task is borderline (could go either way).

    Returns True if the task has characteristics that make it ambiguous
    whether planning is needed.
    """
    prompt_lower = prompt.lower().strip()

    # Very short prompts are often borderline
    if len(prompt_lower) < 30:
        return True

    # Questions might be explanations or implementation requests
    if prompt_lower.endswith("?"):
        return True

    # Vague action verbs without clear scope
    vague_patterns = [
        r"\b(fix|update|change|modify|improve|add|remove|refactor)\b.*\b(something|thing|stuff|it|this|that)\b",
        r"^(fix|update|change|add|remove)\s+\w+$",  # Very short commands
    ]

    for pattern in vague_patterns:
        if re.search(pattern, prompt_lower):
            return True

    # Mentions multiple files/areas but no clear plan
    file_mentions = len(re.findall(r"\b[\w/\\]+\.\w+\b", prompt_lower))
    if 1 <= file_mentions <= 3 and len(prompt_lower) < 100:
        return True

    return False
