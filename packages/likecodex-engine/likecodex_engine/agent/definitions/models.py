"""Pydantic models for agent rules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRule(BaseModel):
    """Schema for a single behavioral rule.

    Rules define patterns that trigger actions (allow/block/modify/redirect)
    based on tool names or event types.
    """

    name: str = Field(..., description="Unique rule name.")
    description: str = Field("", description="Human-readable description of the rule's purpose.")
    pattern: str = Field("*", description="Glob pattern to match against tool names or event types.")
    action: str = Field("allow", description="Action to take: allow, block, modify, redirect, warn.")
    priority: int = Field(0, description="Rule priority (higher = evaluated first).")
    conditions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional list of conditions that must all be true for this rule to apply.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parameters for the action (e.g., redirect_to, keep, message).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata attached to this rule.",
    )
    enabled: bool = Field(True, description="Whether this rule is active.")
    source: str = Field("", description="Source file this rule was loaded from.")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRule:
        return cls(**data)
