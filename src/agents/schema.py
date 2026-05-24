"""Agent configuration schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from context.schema import ContextSpec
from memory.schema import MemorySpec
from models.schema import ModelSpec
from prompts.schema import PromptSpec


class AgentSpec(BaseModel):
    """Agent pipeline configuration."""

    pipeline_id: str = "llm_fixed_v1"
    observation_builder: str = "default"
    context: ContextSpec = Field(default_factory=ContextSpec)
    memory: MemorySpec = Field(default_factory=MemorySpec)
    prompt: PromptSpec
    model: ModelSpec
    parser: str = "strict_json"
    grounding: str = "legal_action_matcher"
    repair: str = "none"
    fallback: str = "first_legal"
