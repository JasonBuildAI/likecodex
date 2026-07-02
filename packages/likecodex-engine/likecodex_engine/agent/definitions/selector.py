"""Agent selector for automatic agent selection based on context."""

from __future__ import annotations

import logging
from typing import Any

from likecodex_engine.agent.definitions.resolver import AgentResolver
from likecodex_engine.agent.definitions.schema import AgentDefinition

logger = logging.getLogger(__name__)


class AgentSelector:
    """Automatically selects the best agent definition for a given context.

    Uses tag matching, priority ordering, and rule evaluation
    to choose the most appropriate agent for the current task.
    """

    def __init__(self, resolver: AgentResolver) -> None:
        self._resolver = resolver
        self._selected: AgentDefinition | None = None

    @property
    def selected(self) -> AgentDefinition | None:
        return self._selected

    def select_for_prompt(self, prompt: str) -> AgentDefinition | None:
        """Select the best agent for a given prompt.

        Uses keyword/tag matching and priority ordering.
        Returns None if no suitable agent is found (use default).
        """
        definitions = self._resolver.get_enabled()
        if not definitions:
            return None

        prompt_lower = prompt.lower()

        # Score each definition
        scored: list[tuple[float, AgentDefinition]] = []
        for definition in definitions:
            score = 0.0

            # Priority base score
            score += definition.priority * 100

            # Tag matching
            for tag in definition.tags:
                tag_lower = tag.lower()
                if tag_lower in prompt_lower:
                    score += 10.0

            # Description matching
            if definition.description:
                desc_keywords = set(definition.description.lower().split())
                prompt_keywords = set(prompt_lower.split())
                overlap = len(desc_keywords & prompt_keywords)
                score += overlap * 5.0

            scored.append((score, definition))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            self._selected = scored[0][1]
            logger.debug(
                "Selected agent '%s' with score %.1f from %d candidates",
                self._selected.name,
                scored[0][0],
                len(scored),
            )
            return self._selected

        return None

    def select_by_name(self, name: str) -> AgentDefinition | None:
        """Select an agent by exact name match."""
        definition = self._resolver.get_by_name(name)
        if definition and definition.enabled:
            self._selected = definition
            return definition
        return None

    def select_by_tag(self, tag: str) -> AgentDefinition | None:
        """Select the highest-priority agent with a specific tag."""
        matches = self._resolver.get_by_tag(tag)
        enabled = [d for d in matches if d.enabled]
        if not enabled:
            return None
        self._selected = max(enabled, key=lambda d: d.priority)
        return self._selected

    def select_default(self) -> AgentDefinition | None:
        """Select the default (highest priority) agent."""
        self._selected = self._resolver.get_default()
        return self._selected

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self._selected.to_dict() if self._selected else None,
            "candidates": len(self._resolver.get_enabled()),
        }
