"""Loader for .likecodex/rules/ YAML rule files."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from likecodex_engine.agent.definitions.models import AgentRule

logger = logging.getLogger(__name__)

# Try to import yaml; fall back to JSON-only parsing
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class RulesLoader:
    """Loads agent rules from .likecodex/rules/ YAML files.

    Supports:
    - Single rule files (.yaml/.yml)
    - Directory scanning for multiple rule files
    - Rule override priority via file naming
    - Auto-detection of .likecodex/rules/ directory
    """

    def __init__(self, working_dir: str) -> None:
        self._working_dir = working_dir
        self._rules_dir = os.path.join(working_dir, ".likecodex", "rules")

    @property
    def rules_dir(self) -> str:
        return self._rules_dir

    def load_all(self) -> list[AgentRule]:
        """Load all rules from the rules directory.

        Scans .likecodex/rules/ for .yaml, .yml, and .json files.
        Returns rules sorted by file name (alphabetical for priority).
        """
        if not os.path.isdir(self._rules_dir):
            logger.debug("Rules directory not found: %s", self._rules_dir)
            return []

        all_rules: list[AgentRule] = []
        rule_files: list[str] = []

        for entry in os.listdir(self._rules_dir):
            if entry.endswith((".yaml", ".yml", ".json")):
                rule_files.append(os.path.join(self._rules_dir, entry))

        rule_files.sort()  # Alphabetical = priority order

        for file_path in rule_files:
            try:
                rules = self.load_file(file_path)
                all_rules.extend(rules)
            except Exception as exc:
                logger.error("Failed to load rules from %s: %s", file_path, exc)

        logger.info("Loaded %d rules from %d files in %s", len(all_rules), len(rule_files), self._rules_dir)
        return all_rules

    def load_file(self, file_path: str) -> list[AgentRule]:
        """Load rules from a single file."""
        path = Path(file_path)
        if not path.exists():
            logger.warning("Rule file not found: %s", file_path)
            return []

        text = path.read_text(encoding="utf-8")
        ext = path.suffix.lower()

        if ext == ".json":
            return self._parse_json(text, file_path)
        if ext in (".yaml", ".yml"):
            return self._parse_yaml(text, file_path)
        return []

    def _parse_yaml(self, text: str, source: str) -> list[AgentRule]:
        if not HAS_YAML:
            logger.error("PyYAML is not installed. Cannot parse %s", source)
            return []
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            logger.error("YAML parse error in %s: %s", source, exc)
            return []
        return self._normalize(data, source)

    def _parse_json(self, text: str, source: str) -> list[AgentRule]:
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error in %s: %s", source, exc)
            return []
        return self._normalize(data, source)

    def _normalize(self, data: Any, source: str) -> list[AgentRule]:
        """Normalize parsed data into AgentRule list."""
        rules: list[AgentRule] = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item["source"] = source
                    try:
                        rules.append(AgentRule(**item))
                    except Exception as exc:
                        logger.warning("Skipping invalid rule in %s: %s", source, exc)
            return rules

        if isinstance(data, dict):
            # Could be a single rule or a dict of named rules
            if "rules" in data:
                return self._normalize(data["rules"], source)
            if "name" in data:
                data["source"] = source
                try:
                    return [AgentRule(**data)]
                except Exception as exc:
                    logger.warning("Invalid rule in %s: %s", source, exc)
                    return []

            # Dict of named rules
            for name, item in data.items():
                if isinstance(item, dict):
                    item["name"] = item.get("name", name)
                    item["source"] = source
                    try:
                        rules.append(AgentRule(**item))
                    except Exception as exc:
                        logger.warning("Skipping rule '%s' in %s: %s", name, source, exc)
            return rules

        return []

    def create_default_rules_dir(self) -> bool:
        """Create the .likecodex/rules/ directory if it doesn't exist.

        Returns True if directory was created, False if it already exists.
        """
        if os.path.isdir(self._rules_dir):
            return False
        try:
            os.makedirs(self._rules_dir, exist_ok=True)
            logger.info("Created rules directory: %s", self._rules_dir)
            return True
        except OSError as exc:
            logger.error("Failed to create rules directory %s: %s", self._rules_dir, exc)
            return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_dir": self._rules_dir,
            "exists": os.path.isdir(self._rules_dir),
        }
