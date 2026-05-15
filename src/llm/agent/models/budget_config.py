"""Prompt budget configuration data models."""

from __future__ import annotations

import math
from dataclasses import dataclass

from llm.agent.models.prompt_block import CompressionState


@dataclass(frozen=True, slots=True)
class PromptBudgetConfig:
    """Prompt budgeting configuration."""

    max_context_tokens: int
    max_output_tokens: int
    context_compression_threshold: float

    def __post_init__(self) -> None:
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if not 0 < self.context_compression_threshold <= 1:
            raise ValueError("context_compression_threshold must be in (0, 1]")
        if self.prompt_budget_tokens <= 0:
            raise ValueError("max_output_tokens leaves no prompt budget")

    @property
    def context_limit_tokens(self) -> int:
        return max(0, math.floor(self.max_context_tokens * self.context_compression_threshold))

    @property
    def prompt_budget_tokens(self) -> int:
        return max(0, self.context_limit_tokens - self.max_output_tokens)