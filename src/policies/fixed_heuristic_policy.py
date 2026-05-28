"""FixedHeuristicPolicy: prioritized action selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.engine.actions import ActionKind
from arena.policy import DecisionContext, PolicyDecision
from policies.first_legal_policy import legal_action_to_action

if TYPE_CHECKING:
    from kernel import Action


# Priority order: higher = more important
ACTION_PRIORITY: dict[ActionKind, int] = {
    ActionKind.TSUMO: 100,       # Self-draw win (highest)
    ActionKind.RON: 99,          # Ron win
    ActionKind.DECLARE_NINE_NINE: 90,  # Nine-nine abort
    # Riichi discards (declare_riichi=True)
    ActionKind.ANKAN: 50,
    ActionKind.KAKAN: 40,
    ActionKind.OPEN_MELD: 30,    # Pon/Chi/Kan
    ActionKind.DISCARD: 20,      # Regular discard
    ActionKind.DRAW: 10,
    ActionKind.PASS_CALL: 5,
    ActionKind.BEGIN_ROUND: 1,
    ActionKind.NEXT_ROUND: 1,
    ActionKind.NOOP: 0,
    ActionKind.CALL_PASS_DRAIN: 0,
}


class FixedHeuristicPolicy:
    """Policy that selects actions by priority: TSUMO > RON > Riichi > Discard > Draw."""

    name: str = "fixed_heuristic"

    def __init__(self, policy_id: str) -> None:
        self.policy_id = policy_id

    def decide(self, ctx: DecisionContext) -> PolicyDecision:
        """Select highest priority legal action."""
        if not ctx.legal_actions:
            msg = "FixedHeuristicPolicy: legal_actions is empty"
            raise ValueError(msg)

        # Score each legal action
        def score(legal) -> int:
            base = ACTION_PRIORITY.get(legal.kind, 0)
            # Riichi discards get bonus
            if legal.kind == ActionKind.DISCARD and legal.declare_riichi:
                base += 60  # Riichi is higher than regular discard
            return base

        # Sort by score (descending), pick highest
        sorted_actions = sorted(ctx.legal_actions, key=score, reverse=True)
        legal = sorted_actions[0]
        action = legal_action_to_action(legal)
        return PolicyDecision(action=action)