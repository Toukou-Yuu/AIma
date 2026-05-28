"""Prompt DSL configuration schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PromptSectionSpec(BaseModel):
    """Prompt section configuration."""

    id: str
    enabled: bool = True
    variant: str | None = None
    renderer: str | None = None
    source: str | None = None
    max_items: int | None = None
    max_tokens: int | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class PromptBudgetSpec(BaseModel):
    """Prompt token budget configuration."""

    max_prompt_tokens: int | None = None
    truncation_policy: str = "drop_oldest_public_events"


class PromptSpec(BaseModel):
    """Prompt configuration."""

    template_id: str
    version: str
    output_format: Literal["json_action", "natural_action"] = "json_action"
    sections: list[PromptSectionSpec]
    budget: PromptBudgetSpec = Field(default_factory=PromptBudgetSpec)
