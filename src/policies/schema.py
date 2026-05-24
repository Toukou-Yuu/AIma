"""Policy configuration schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.schema import AgentSpec


class PolicySpec(BaseModel):
    """Policy configuration."""

    type: Literal["random", "first_legal", "fixed_heuristic", "llm"]
    id: str
    agent: AgentSpec | None = None
    options: dict[str, Any] = Field(default_factory=dict)
