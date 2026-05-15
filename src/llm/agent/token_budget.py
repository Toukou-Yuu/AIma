"""Token estimation and prompt budget planning.

This module provides transition exports for backwards compatibility.
New code should import from llm.agent.models.* and llm.agent.services.* instead.
"""

from __future__ import annotations

# Re-export from models for backwards compatibility
from llm.agent.models.budget_config import PromptBudgetConfig
from llm.agent.models.diagnostics import (
    BlockTokenUsage,
    PromptDiagnostics,
    PromptDiagnosticsSummary,
    summarize_prompt_diagnostics,
)
from llm.agent.models.prompt_block import (
    CompressionState,
    PromptBlock,
    PromptBlockVariant,
    SelectedPromptBlock,
    _COMPRESSION_ORDER,
)

# Re-export from services for backwards compatibility
from llm.agent.services.budget_planner import PromptBudgetPlanner, PromptPlan
from llm.agent.services.token_estimator import TokenEstimateService


# Maintain original __all__ for backwards compatibility
__all__ = [
    "BlockTokenUsage",
    "CompressionState",
    "PromptBlock",
    "PromptBlockVariant",
    "PromptBudgetConfig",
    "PromptBudgetPlanner",
    "PromptDiagnostics",
    "PromptDiagnosticsSummary",
    "PromptPlan",
    "SelectedPromptBlock",
    "TokenEstimateService",
    "summarize_prompt_diagnostics",
]