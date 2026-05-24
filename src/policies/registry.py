"""PolicyRegistry: factory for creating Policy instances."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.policy import Policy
    from policies.schema import PolicySpec


# PolicyFactory: (spec, seed) -> Policy
PolicyFactory = Callable[["PolicySpec", int], "Policy"]


class PolicyRegistry:
    """Registry mapping policy type strings to factory functions."""

    def __init__(self) -> None:
        self._factories: dict[str, PolicyFactory] = {}

    def register(self, policy_type: str, factory: PolicyFactory) -> None:
        """Register a factory for a policy type."""
        if policy_type in self._factories:
            raise ValueError(f"Policy type '{policy_type}' already registered")
        self._factories[policy_type] = factory

    def create(self, spec: "PolicySpec", seed: int) -> "Policy":
        """Create a Policy instance from PolicySpec."""
        if spec.type not in self._factories:
            raise ValueError(f"Unknown policy type: {spec.type}")
        return self._factories[spec.type](spec, seed)


# Global registry
REGISTRY = PolicyRegistry()


def register_builtin_policies() -> None:
    """Register all built-in policies (idempotent)."""
    from policies.first_legal_policy import FirstLegalPolicy
    from policies.random_policy import RandomPolicy
    from policies.fixed_heuristic_policy import FixedHeuristicPolicy

    # Idempotent: skip if already registered
    if "first_legal" not in REGISTRY._factories:
        REGISTRY.register("first_legal", lambda spec, seed: FirstLegalPolicy(spec.id))
    if "random" not in REGISTRY._factories:
        REGISTRY.register("random", lambda spec, seed: RandomPolicy(spec.id, seed))
    if "fixed_heuristic" not in REGISTRY._factories:
        REGISTRY.register("fixed_heuristic", lambda spec, seed: FixedHeuristicPolicy(spec.id))