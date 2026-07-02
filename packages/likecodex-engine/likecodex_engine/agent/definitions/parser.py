"""YAML parser for AGENTS.md agent definitions."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from likecodex_engine.agent.definitions.schema import AgentDefinition

logger = logging.getLogger(__name__)

# Try to import yaml; fall back to JSON-only parsing
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class AgentDefinitionParser:
    """Parses agent definitions from YAML/JSON/Markdown sources.

    Supports:
    - Standalone .yaml/.yml files
    - AGENTS.md files with YAML frontmatter blocks
    - JSON definition files
    - Embedded YAML in markdown fenced blocks
    """

    def __init__(self, agents_file: str | None = None) -> None:
        self.agents_file = agents_file

    def parse_file(self, file_path: str) -> list[AgentDefinition]:
        """Parse agent definitions from a file.

        Supports .yaml, .yml, .json, and .md files.
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning("Agents file not found: %s", file_path)
            return []

        ext = path.suffix.lower()
        try:
            if ext in (".yaml", ".yml"):
                return self._parse_yaml_file(path)
            if ext == ".json":
                return self._parse_json_file(path)
            if ext == ".md":
                return self._parse_markdown_file(path)
            logger.warning("Unsupported file extension: %s", ext)
            return []
        except Exception as exc:
            logger.error("Failed to parse agents file %s: %s", file_path, exc)
            return []

    def parse_text(self, text: str, source: str = "<text>") -> list[AgentDefinition]:
        """Parse agent definitions from raw text (YAML or JSON)."""
        text = text.strip()
        if not text:
            return []

        if text.startswith("{"):
            return self._parse_json_text(text, source)
        return self._parse_yaml_text(text, source)

    def _parse_yaml_file(self, path: Path) -> list[AgentDefinition]:
        if not HAS_YAML:
            logger.error("PyYAML is not installed. Cannot parse %s", path)
            return []
        text = path.read_text(encoding="utf-8")
        return self._parse_yaml_text(text, str(path))

    def _parse_json_file(self, path: Path) -> list[AgentDefinition]:
        text = path.read_text(encoding="utf-8")
        return self._parse_json_text(text, str(path))

    def _parse_markdown_file(self, path: Path) -> list[AgentDefinition]:
        """Parse AGENTS.md file - extracts YAML/JSON from fenced code blocks."""
        text = path.read_text(encoding="utf-8")
        definitions: list[AgentDefinition] = []

        # Extract YAML frontmatter (between --- delimiters)
        frontmatter = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if frontmatter:
            yaml_text = frontmatter.group(1).strip()
            if yaml_text:
                definitions.extend(self.parse_text(yaml_text, str(path)))

        # Extract fenced code blocks with yaml/json language tags
        for match in re.finditer(r"```(?:yaml|yml|json)\s*\n(.*?)\n```", text, re.DOTALL):
            block_text = match.group(1).strip()
            if block_text:
                definitions.extend(self.parse_text(block_text, str(path)))

        return definitions

    def _parse_yaml_text(self, text: str, source: str) -> list[AgentDefinition]:
        if not HAS_YAML:
            return []
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            logger.error("YAML parse error in %s: %s", source, exc)
            return []
        return self._normalize_to_list(data, source)

    def _parse_json_text(self, text: str, source: str) -> list[AgentDefinition]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error in %s: %s", source, exc)
            return []
        return self._normalize_to_list(data, source)

    def _normalize_to_list(self, data: Any, source: str) -> list[AgentDefinition]:
        """Normalize parsed data into a list of AgentDefinitions."""
        if isinstance(data, list):
            definitions = []
            for item in data:
                if isinstance(item, dict):
                    item["source"] = source
                    try:
                        definitions.append(AgentDefinition(**item))
                    except Exception as exc:
                        logger.warning("Skipping invalid agent definition in %s: %s", source, exc)
            return definitions
        if isinstance(data, dict):
            # Could be a single definition or a dict of definitions
            if "agents" in data:
                return self._normalize_to_list(data["agents"], source)
            if "name" in data:
                data["source"] = source
                try:
                    return [AgentDefinition(**data)]
                except Exception as exc:
                    logger.warning("Invalid agent definition in %s: %s", source, exc)
            # Dict of named agents
            definitions = []
            for name, item in data.items():
                if isinstance(item, dict):
                    item["name"] = item.get("name", name)
                    item["source"] = source
                    try:
                        definitions.append(AgentDefinition(**item))
                    except Exception as exc:
                        logger.warning("Skipping agent '%s' in %s: %s", name, source, exc)
            return definitions
        return []


def find_agents_file(working_dir: str) -> str | None:
    """Find the AGENTS.md or agents.yaml file in the given directory."""
    candidates = [
        os.path.join(working_dir, "AGENTS.md"),
        os.path.join(working_dir, "agents.yaml"),
        os.path.join(working_dir, "agents.yml"),
        os.path.join(working_dir, "agents.json"),
        os.path.join(working_dir, ".likecodex", "agents.yaml"),
        os.path.join(working_dir, ".likecodex", "agents.yml"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None
