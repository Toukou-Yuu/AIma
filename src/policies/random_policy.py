"""RandomPolicy: randomly select a legal action using seed."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from arena.policy import DecisionContext, PolicyDecision
from policies.first_legal_policy import legal_action_to_action

if TYPE_CHECKING:
    from kernel import Action


class RandomPolicy:
    """Policy that randomly selects a legal action using derived seed."""

    name: str = "random"

    def __init__(self, policy_id: str, seed: int) -> None:
        self.policy_id = policy_id
        self._rng = random.Random(seed)

    def decide(self, ctx: DecisionContext) -> PolicyDecision:
        """Randomly select a legal action."""
        if not ctx.legal_actions:
            msg = "RandomPolicy: legal_actions is empty"
            raise ValueError(msg)

        legal = self._rng.choice(ctx.legal_actions)
        action = legal_action_to_action(legal)
        return PolicyDecision(action=action)