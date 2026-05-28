"""FirstLegalPolicy: 选择第一个合法动作的简单策略。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arena.policy import DecisionContext, PolicyDecision

if TYPE_CHECKING:
    from kernel import Action
    from kernel.api import LegalAction


def legal_action_to_action(legal: LegalAction) -> Action:
    """将 LegalAction 转换为 Action。

    Args:
        legal: 合法动作

    Returns:
        对应的 Action 对象
    """
    from kernel import Action

    return Action(
        kind=legal.kind,
        seat=legal.seat,
        tile=legal.tile,
        meld=legal.meld,
        declare_riichi=legal.declare_riichi,
    )


class FirstLegalPolicy:
    """始终选择 legal_actions[0] 的策略。

    用于测试和基准对照。
    """

    name: str = "first_legal"

    def __init__(self, policy_id: str) -> None:
        self.policy_id = policy_id

    def decide(self, ctx: DecisionContext) -> PolicyDecision:
        """返回第一个合法动作。"""
        if not ctx.legal_actions:
            msg = "FirstLegalPolicy: legal_actions is empty"
            raise ValueError(msg)

        action = legal_action_to_action(ctx.legal_actions[0])
        return PolicyDecision(action=action)