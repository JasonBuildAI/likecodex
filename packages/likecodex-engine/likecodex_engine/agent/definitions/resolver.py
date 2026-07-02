"""Agent resolver for parsing and selecting the correct agent definition."""

from __future__ import annotations

import logging
from typing import Any

from likecodex_engine.agent.definitions.parser import (
    AgentDefinitionParser,
    find_agents_file,
)
from likecodex_engine.agent.definitions.schema import AgentDefinition

logger = logging.getLogger(__name__)


class AgentResolver:
    """Resolves agent definitions from project configuration files.

    Handles loading, caching, and selecting agent definitions
    based on the current working directory and project context.
    """

    def __init__(self, working_dir: str) -> None:
        self._working_dir = working_dir
        self._parser = AgentDefinitionParser()
        self._definitions: list[AgentDefinition] = []
        self._loaded: bool = False

    @property
    def definitions(self) -> list[AgentDefinition]:
        if not self._loaded:
            self.load()
        return list(self._definitions)

    def load(self, file_path: str | None = None) -> list[AgentDefinition]:
        """Load agent definitions from a file or auto-detect."""
        path = file_path or find_agents_file(self._working_dir)
        if not path:
            logger.debug("No agents file found in %s", self._working_dir)
            self._loaded = True
            return []

        self._definitions = self._parser.parse_file(path)
        self._loaded = True
        logger.info("Loaded %d agent definitions from %s", len(self._definitions), path)
        return self._definitions

    def reload(self, file_path: str | None = None) -> list[AgentDefinition]:
        """Force reload agent definitions."""
        self._loaded = False
        return self.load(file_path)

    def get_by_name(self, name: str) -> AgentDefinition | None:
        """Find an agent definition by name."""
        for definition in self.definitions:
            if definition.name == name:
                return definition
        return None

    def get_by_tag(self, tag: str) -> list[AgentDefinition]:
        """Find all agent definitions with a specific tag."""
        return [d for d in self.definitions if tag in d.tags]

    def get_enabled(self) -> list[AgentDefinition]:
        """Get all enabled agent definitions."""
        return [d for d in self.definitions if d.enabled]

    def get_default(self) -> AgentDefinition | None:
        """Get the default agent definition (highest priority, enabled)."""
        enabled = self.get_enabled()
        if not enabled:
            return None
        return max(enabled, key=lambda d: d.priority)

    def to_dict(self) -> dict[str, Any]:
        return {
            "working_dir": self._working_dir,
            "loaded": self._loaded,
            "count": len(self._definitions),
            "definitions": [d.to_dict() for d in self._definitions],
        }
