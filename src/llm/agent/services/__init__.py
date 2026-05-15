"""Services package for LLM agent module.

This package contains service classes extracted from token_budget.py and context.py:
- TokenEstimateService: Token estimation from text
- PromptBudgetPlanner: Budget-aware prompt block selection
- Action descriptor functions: Describe actions as readable text
"""

from llm.agent.services.action_descriptor import (
    describe_action,
    describe_action_summary,
)
from llm.agent.services.budget_planner import PromptBudgetPlanner, PromptPlan
from llm.agent.services.token_estimator import TokenEstimateService

__all__ = [
    "describe_action",
    "describe_action_summary",
    "PromptBudgetPlanner",
    "PromptPlan",
    "TokenEstimateService",
]