"""Agent definitions module.

Provides the complete system for defining, parsing, validating,
and selecting agent configurations based on rules and context.
"""

from likecodex_engine.agent.definitions.hot_reload import HotReloadWatcher
from likecodex_engine.agent.definitions.models import AgentRule
from likecodex_engine.agent.definitions.parser import (
    AgentDefinitionParser,
)
from likecodex_engine.agent.definitions.resolver import AgentResolver
from likecodex_engine.agent.definitions.rules_engine import RulesEngine
from likecodex_engine.agent.definitions.rules_loader import RulesLoader
from likecodex_engine.agent.definitions.schema import AgentDefinition
from likecodex_engine.agent.definitions.selector import AgentSelector
from likecodex_engine.agent.definitions.validator import (
    RuleConflict,
    RuleValidator,
    ValidationResult,
)

__all__ = [
    "AgentDefinition",
    "AgentDefinitionParser",
    "AgentResolver",
    "AgentRule",
    "AgentSelector",
    "HotReloadWatcher",
    "RuleConflict",
    "RuleValidator",
    "RulesEngine",
    "RulesLoader",
    "ValidationResult",
]
