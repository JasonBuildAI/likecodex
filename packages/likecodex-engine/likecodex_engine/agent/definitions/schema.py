"""Agent definition schema using Pydantic models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    """Schema for an agent definition (parsed from YAML/JSON).

    Defines the complete specification for an agent instance,
    including its identity, model configuration, tool permissions,
    and behavioral rules.
    """

    name: str = Field(..., description="Unique agent name.")
    description: str = Field("", description="Human-readable description of the agent's purpose.")
    version: str = Field("1.0", description="Schema version for this definition.")

    # Model configuration
    model: str = Field("default", description="LLM model identifier to use.")
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="LLM temperature override.")
    max_tokens: int | None = Field(None, ge=1, description="Max output tokens override.")
    reasoning_depth: str | None = Field(
        None, description="Reasoning depth override (quick_qa, light, standard, deep, full)."
    )

    # Tool configuration
    allowed_tools: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of allowed tool names. '*' means all tools.",
    )
    blocked_tools: list[str] = Field(
        default_factory=list,
        description="List of explicitly blocked tool names.",
    )
    read_only: bool = Field(False, description="If True, only read-only tools are allowed.")

    # Behavioral rules
    rules: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of behavioral rules for this agent.",
    )
    max_iterations: int | None = Field(None, ge=1, description="Override max loop iterations.")
    system_prompt_extra: str = Field("", description="Extra system prompt content appended to base prompt.")
    agent_mode: str = Field("agent", description="Agent mode: agent, ask, manual, plan.")

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for categorization/selection.")
    priority: int = Field(0, description="Selection priority (higher = selected first).")
    source: str = Field("", description="Source file path this definition was loaded from.")
    enabled: bool = Field(True, description="Whether this agent definition is active.")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentDefinition:
        return cls(**data)
