"""PolicyRegistry: factory for creating Policy instances."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.policy import Policy
    from memory.stores import MemoryStore
    from policies.schema import PolicySpec


@dataclass(frozen=True, slots=True)
class PolicyFactoryContext:
    """Runtime objects shared while constructing policies for one job."""

    seed: int
    memory_store: "MemoryStore | None" = None
    memory_enabled: bool = True


PolicyFactory = Callable[["PolicySpec", PolicyFactoryContext], "Policy"]


class PolicyRegistry:
    """Registry mapping policy type strings to factory functions."""

    def __init__(self) -> None:
        self._factories: dict[str, PolicyFactory] = {}

    def register(self, policy_type: str, factory: PolicyFactory) -> None:
        """Register a factory for a policy type."""
        if policy_type in self._factories:
            raise ValueError(f"Policy type '{policy_type}' already registered")
        self._factories[policy_type] = factory

    def create(self, spec: "PolicySpec", context: PolicyFactoryContext) -> "Policy":
        """Create a Policy instance from PolicySpec."""
        if spec.type not in self._factories:
            raise ValueError(f"Unknown policy type: {spec.type}")
        return self._factories[spec.type](spec, context)


# Global registry
REGISTRY = PolicyRegistry()


def register_builtin_policies() -> None:
    """Register all built-in policies (idempotent)."""
    from policies.first_legal_policy import FirstLegalPolicy
    from policies.fixed_heuristic_policy import FixedHeuristicPolicy
    from policies.llm_policy import LLMPolicy
    from policies.random_policy import RandomPolicy

    def build_llm_policy(spec, ctx):
        if spec.agent is None:
            msg = f"LLM policy '{spec.id}' requires an agent spec"
            raise ValueError(msg)
        return LLMPolicy(
            policy_id=spec.id,
            spec=spec.agent,
            seed=ctx.seed,
            memory_store=ctx.memory_store,
            memory_enabled=ctx.memory_enabled,
        )

    # Idempotent: skip if already registered
    if "first_legal" not in REGISTRY._factories:
        REGISTRY.register("first_legal", lambda spec, ctx: FirstLegalPolicy(spec.id))
    if "random" not in REGISTRY._factories:
        REGISTRY.register("random", lambda spec, ctx: RandomPolicy(spec.id, ctx.seed))
    if "fixed_heuristic" not in REGISTRY._factories:
        REGISTRY.register("fixed_heuristic", lambda spec, ctx: FixedHeuristicPolicy(spec.id))
    if "llm" not in REGISTRY._factories:
        REGISTRY.register("llm", build_llm_policy)
