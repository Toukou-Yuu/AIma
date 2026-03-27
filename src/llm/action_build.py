"""``LegalAction`` → ``apply`` 用 ``Action``。"""

from __future__ import annotations

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import Action, ActionKind


def legal_action_to_action(la: LegalAction) -> Action:
    """将枚举出的合法动作转为引擎输入。"""
    k = la.kind
    if k == ActionKind.NOOP:
        return Action(ActionKind.NOOP, seat=la.seat)
    if k == ActionKind.DRAW:
        return Action(ActionKind.DRAW, seat=la.seat)
    if k == ActionKind.DISCARD:
        if la.tile is None:
            msg = "DISCARD LegalAction requires tile"
            raise ValueError(msg)
        return Action(
            ActionKind.DISCARD,
            seat=la.seat,
            tile=la.tile,
            declare_riichi=la.declare_riichi,
        )
    if k == ActionKind.PASS_CALL:
        return Action(ActionKind.PASS_CALL, seat=la.seat)
    if k == ActionKind.RON:
        return Action(ActionKind.RON, seat=la.seat)
    if k == ActionKind.TSUMO:
        return Action(
            ActionKind.TSUMO,
            seat=la.seat,
            tile=la.tile,
        )
    if k == ActionKind.OPEN_MELD:
        if la.meld is None:
            msg = "OPEN_MELD LegalAction requires meld"
            raise ValueError(msg)
        return Action(ActionKind.OPEN_MELD, seat=la.seat, meld=la.meld)
    if k == ActionKind.ANKAN:
        if la.meld is None:
            msg = "ANKAN LegalAction requires meld"
            raise ValueError(msg)
        return Action(ActionKind.ANKAN, seat=la.seat, meld=la.meld)
    if k == ActionKind.SHANKUMINKAN:
        if la.meld is None:
            msg = "SHANKUMINKAN LegalAction requires meld"
            raise ValueError(msg)
        return Action(ActionKind.SHANKUMINKAN, seat=la.seat, meld=la.meld)
    msg = f"unsupported LegalAction.kind: {k!r}"
    raise ValueError(msg)
