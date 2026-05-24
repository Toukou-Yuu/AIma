"""Policies module: player strategy implementations."""

from policies.schema import PolicySpec
from policies.first_legal_policy import FirstLegalPolicy, legal_action_to_action
from policies.random_policy import RandomPolicy
from policies.fixed_heuristic_policy import FixedHeuristicPolicy
from policies.llm_policy import LLMPolicy
from policies.registry import PolicyRegistry, REGISTRY, register_builtin_policies

__all__ = [
    "PolicySpec",
    "FirstLegalPolicy",
    "RandomPolicy",
    "FixedHeuristicPolicy",
    "LLMPolicy",
    "legal_action_to_action",
    "PolicyRegistry",
    "REGISTRY",
    "register_builtin_policies",
]
