"""Tests for agent definitions: parser, rules engine, validator, selector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from likecodex_engine.agent.definitions.models import AgentRule
from likecodex_engine.agent.definitions.parser import AgentDefinitionParser, find_agents_file
from likecodex_engine.agent.definitions.resolver import AgentResolver
from likecodex_engine.agent.definitions.rules_engine import RulesEngine
from likecodex_engine.agent.definitions.schema import AgentDefinition
from likecodex_engine.agent.definitions.selector import AgentSelector
from likecodex_engine.agent.definitions.validator import RuleConflict, RuleValidator, ValidationResult


# ── AgentDefinition data model tests ────────────────────────────

class TestAgentDefinition:
    """Tests for AgentDefinition Pydantic model."""

    def test_minimal_definition(self) -> None:
        d = AgentDefinition(name="test-agent")
        assert d.name == "test-agent"
        assert d.enabled is True
        assert d.priority == 0
        assert d.allowed_tools == ["*"]
        assert d.agent_mode == "agent"

    def test_to_dict(self) -> None:
        d = AgentDefinition(name="coder", priority=10, tags=["rust", "backend"])
        data = d.to_dict()
        assert data["name"] == "coder"
        assert data["priority"] == 10
        assert data["tags"] == ["rust", "backend"]

    def test_from_dict(self) -> None:
        d = AgentDefinition.from_dict({
            "name": "helper",
            "description": "General helper",
            "priority": 5,
        })
        assert d.name == "helper"
        assert d.description == "General helper"
        assert d.priority == 5

    def test_invalid_temperature(self) -> None:
        with pytest.raises(Exception):
            AgentDefinition(name="bad", temperature=5.0)  # above 2.0

    def test_invalid_max_tokens(self) -> None:
        with pytest.raises(Exception):
            AgentDefinition(name="bad", max_tokens=0)  # below 1


# ── AgentRule model tests ───────────────────────────────────────

class TestAgentRule:
    """Tests for AgentRule Pydantic model."""

    def test_minimal_rule(self) -> None:
        r = AgentRule(name="block-write")
        assert r.pattern == "*"
        assert r.action == "allow"
        assert r.enabled is True

    def test_to_dict(self) -> None:
        r = AgentRule(name="test", action="block", priority=10)
        data = r.to_dict()
        assert data["name"] == "test"
        assert data["action"] == "block"

    def test_from_dict(self) -> None:
        r = AgentRule.from_dict({"name": "custom", "action": "redirect", "params": {"redirect_to": "ask"}})
        assert r.action == "redirect"
        assert r.params["redirect_to"] == "ask"


# ── AgentDefinitionParser tests ─────────────────────────────────

class TestAgentDefinitionParser:
    """Tests for AgentDefinitionParser."""

    def test_parse_text_json(self) -> None:
        parser = AgentDefinitionParser()
        text = '[{"name": "agent1", "description": "Test agent"}]'
        definitions = parser.parse_text(text)
        assert len(definitions) == 1
        assert definitions[0].name == "agent1"

    def test_parse_text_yaml(self) -> None:
        parser = AgentDefinitionParser()
        text = """
- name: analyst
  description: Code analyst
  priority: 5
"""
        definitions = parser.parse_text(text)
        assert len(definitions) == 1
        assert definitions[0].name == "analyst"

    def test_parse_text_empty(self) -> None:
        parser = AgentDefinitionParser()
        assert parser.parse_text("") == []
        assert parser.parse_text("   ") == []

    def test_parse_text_invalid_json(self) -> None:
        parser = AgentDefinitionParser()
        result = parser.parse_text("{invalid}")
        assert result == []

    def test_parse_text_agents_key(self) -> None:
        parser = AgentDefinitionParser()
        text = '{"agents": [{"name": "sub-agent"}]}'
        definitions = parser.parse_text(text)
        assert len(definitions) == 1
        assert definitions[0].name == "sub-agent"

    def test_parse_text_named_dict(self) -> None:
        parser = AgentDefinitionParser()
        text = '{"worker": {"description": "Worker agent"}}'
        definitions = parser.parse_text(text)
        assert len(definitions) == 1
        assert definitions[0].name == "worker"

    def test_find_agents_file_no_match(self, tmp_path: Path) -> None:
        result = find_agents_file(str(tmp_path))
        assert result is None

    def test_find_agents_file_found(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# Agents")
        result = find_agents_file(str(tmp_path))
        assert result == str(tmp_path / "AGENTS.md")


# ── AgentResolver tests ─────────────────────────────────────────

class TestAgentResolver:
    """Tests for AgentResolver."""

    def test_init_empty(self, tmp_path: Path) -> None:
        resolver = AgentResolver(str(tmp_path))
        assert resolver.definitions == []

    def test_get_enabled(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [
            AgentDefinition(name="a", enabled=True),
            AgentDefinition(name="b", enabled=False),
            AgentDefinition(name="c", enabled=True),
        ]
        resolver._loaded = True
        enabled = resolver.get_enabled()
        assert len(enabled) == 2
        assert all(d.enabled for d in enabled)

    def test_get_by_name(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [AgentDefinition(name="finder")]
        resolver._loaded = True
        assert resolver.get_by_name("finder") is not None
        assert resolver.get_by_name("missing") is None

    def test_get_default_highest_priority(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [
            AgentDefinition(name="low", priority=1, enabled=True),
            AgentDefinition(name="high", priority=10, enabled=True),
        ]
        resolver._loaded = True
        default = resolver.get_default()
        assert default is not None
        assert default.name == "high"

    def test_get_default_no_enabled(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._loaded = True
        assert resolver.get_default() is None

    def test_reload(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [AgentDefinition(name="old")]
        resolver._loaded = True
        with patch.object(resolver._parser, "parse_file", return_value=[AgentDefinition(name="new")]):
            resolver.reload()
        assert resolver.definitions[0].name == "new"


# ── RulesEngine tests ───────────────────────────────────────────

class TestRulesEngine:
    """Tests for RulesEngine."""

    def test_load_rules(self) -> None:
        engine = RulesEngine()
        rules = [AgentRule(name="r1"), AgentRule(name="r2")]
        engine.load_rules(rules)
        assert len(engine.rules) == 2

    def test_add_rule(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="new-rule"))
        assert len(engine.rules) == 1

    def test_is_allowed_no_rules(self) -> None:
        engine = RulesEngine()
        assert engine.is_allowed("write_file") is True

    def test_is_allowed_blocked(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="block-write", pattern="write_*", action="block"))
        assert engine.is_allowed("write_file") is False
        assert engine.is_allowed("read_file") is True

    def test_evaluate_pattern_glob(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="block-all-writes", pattern="write_*", action="block"))
        results = engine.evaluate("write_file")
        assert len(results) == 1
        assert results[0]["action"] == "block"

    def test_evaluate_wildcard(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="block-all", pattern="*", action="block"))
        results = engine.evaluate("anything")
        assert len(results) == 1
        assert results[0]["action"] == "block"

    def test_disabled_rule_skipped(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="disabled", pattern="*", action="block", enabled=False))
        assert engine.is_allowed("anything") is True

    def test_priority_ordering(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="low", pattern="*", action="allow", priority=1))
        engine.add_rule(AgentRule(name="high", pattern="*", action="block", priority=10))
        results = engine.evaluate("test")
        assert results[0]["rule_name"] == "high"

    def test_get_effective_tools(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="block-write", pattern="write_*", action="block"))
        tools = engine.get_effective_tools(["read_file", "write_file", "run_command"])
        assert "read_file" in tools
        assert "write_file" not in tools
        assert "run_command" in tools

    def test_clear_rules(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(name="test"))
        engine.clear()
        assert engine.rules == []

    def test_condition_operators(self) -> None:
        engine = RulesEngine()
        # eq
        engine.add_rule(AgentRule(
            name="eq-check", pattern="*", action="block",
            conditions=[{"field": "env", "op": "eq", "value": "production"}],
        ))
        assert engine.is_allowed("test", {"env": "production"}) is False
        assert engine.is_allowed("test", {"env": "dev"}) is True

    def test_condition_exists(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(
            name="exists-check", pattern="*", action="block",
            conditions=[{"field": "user.role", "op": "exists"}],
        ))
        assert engine.is_allowed("test", {"user": {"role": "admin"}}) is False
        assert engine.is_allowed("test", {}) is True

    def test_condition_matches(self) -> None:
        engine = RulesEngine()
        engine.add_rule(AgentRule(
            name="match-check", pattern="*", action="block",
            conditions=[{"field": "name", "op": "matches", "value": r"^test-\d{3}$"}],
        ))
        assert engine.is_allowed("test", {"name": "test-123"}) is False
        assert engine.is_allowed("test", {"name": "other"}) is True


# ── RuleValidator tests ─────────────────────────────────────────

class TestRuleValidator:
    """Tests for RuleValidator."""

    def test_validate_definition_ok(self) -> None:
        validator = RuleValidator()
        definition = AgentDefinition(
            name="valid-agent",
            description="A valid agent",
            temperature=0.5,
            max_tokens=4096,
            agent_mode="agent",
        )
        result = validator.validate_definition(definition)
        assert result.valid is True

    def test_validate_definition_no_name(self) -> None:
        validator = RuleValidator()
        definition = AgentDefinition(name="")
        result = validator.validate_definition(definition)
        assert result.valid is False
        assert any("name" in e for e in result.errors)

    def test_validate_definition_bad_mode(self) -> None:
        validator = RuleValidator()
        definition = AgentDefinition(name="bad", agent_mode="invalid")
        result = validator.validate_definition(definition)
        assert result.valid is False

    def test_validate_rule_ok(self) -> None:
        validator = RuleValidator()
        rule = AgentRule(name="test-rule", action="allow")
        result = validator.validate_rule(rule)
        assert result.valid is True

    def test_validate_rule_bad_action(self) -> None:
        validator = RuleValidator()
        rule = AgentRule(name="bad", action="destroy")
        result = validator.validate_rule(rule)
        assert result.valid is False

    def test_detect_conflicts_same_priority(self) -> None:
        validator = RuleValidator()
        rules = [
            AgentRule(name="allow-all", pattern="*", action="allow", priority=0),
            AgentRule(name="block-all", pattern="*", action="block", priority=0),
        ]
        conflicts = validator.detect_conflicts(rules)
        assert len(conflicts) == 1
        assert conflicts[0].severity == "error"

    def test_detect_conflicts_diff_priority(self) -> None:
        validator = RuleValidator()
        rules = [
            AgentRule(name="allow-all", pattern="*", action="allow", priority=10),
            AgentRule(name="block-all", pattern="*", action="block", priority=0),
        ]
        conflicts = validator.detect_conflicts(rules)
        assert len(conflicts) == 1
        assert conflicts[0].severity == "warning"

    def test_validate_definitions_duplicate_name(self) -> None:
        validator = RuleValidator()
        definitions = [
            AgentDefinition(name="dup", source="file1.yaml"),
            AgentDefinition(name="dup", source="file2.yaml"),
        ]
        result = validator.validate_definitions(definitions)
        assert any("duplicate" in w.lower() for w in result.warnings)

    def test_validation_result_merge(self) -> None:
        r1 = ValidationResult()
        r1.add_error("err1")
        r2 = ValidationResult()
        r2.add_warning("warn1")
        r1.merge(r2)
        assert r1.valid is False
        assert len(r1.errors) == 1
        assert len(r1.warnings) == 1


# ── AgentSelector tests ─────────────────────────────────────────

class TestAgentSelector:
    """Tests for AgentSelector."""

    def test_select_for_prompt_tag_match(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [
            AgentDefinition(name="rust-dev", tags=["rust"], priority=1, enabled=True),
            AgentDefinition(name="python-dev", tags=["python"], priority=1, enabled=True),
        ]
        resolver._loaded = True
        selector = AgentSelector(resolver)
        selected = selector.select_for_prompt("I need help with Rust code")
        assert selected is not None
        assert selected.name == "rust-dev"

    def test_select_for_prompt_no_match(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._loaded = True
        selector = AgentSelector(resolver)
        assert selector.select_for_prompt("anything") is None

    def test_select_by_name(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [AgentDefinition(name="specific-agent", enabled=True)]
        resolver._loaded = True
        selector = AgentSelector(resolver)
        assert selector.select_by_name("specific-agent") is not None
        assert selector.select_by_name("missing") is None

    def test_select_by_tag(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [
            AgentDefinition(name="a", tags=["backend"], priority=5, enabled=True),
            AgentDefinition(name="b", tags=["backend"], priority=10, enabled=True),
        ]
        resolver._loaded = True
        selector = AgentSelector(resolver)
        selected = selector.select_by_tag("backend")
        assert selected is not None
        assert selected.name == "b"  # highest priority

    def test_select_default(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [
            AgentDefinition(name="top", priority=100, enabled=True),
            AgentDefinition(name="low", priority=1, enabled=True),
        ]
        resolver._loaded = True
        selector = AgentSelector(resolver)
        selected = selector.select_default()
        assert selected is not None
        assert selected.name == "top"

    def test_selected_property(self) -> None:
        resolver = AgentResolver("/tmp")
        resolver._definitions = [AgentDefinition(name="selected-agent", enabled=True)]
        resolver._loaded = True
        selector = AgentSelector(resolver)
        selector.select_by_name("selected-agent")
        assert selector.selected is not None
        assert selector.selected.name == "selected-agent"
