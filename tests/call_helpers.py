"""测试用：跳过整段舍牌应答窗口。"""

from __future__ import annotations

from kernel.call import apply_pass_call
from kernel.deal.model import BoardState
from kernel.engine.state import GameState
from kernel.play.model import TurnPhase, kamicha_seat


def clear_call_window(board: BoardState) -> BoardState:
    """荣和 pass → 碰杠 pass → 吃 pass，直至 ``NEED_DRAW``。"""
    b = board
    while b.turn_phase == TurnPhase.CALL_RESPONSE:
        cs = b.call_state
        assert cs is not None
        if cs.stage == "ron":
            s = next(iter(cs.ron_remaining))
            b = apply_pass_call(b, s)
        elif cs.stage == "pon_kan":
            b = apply_pass_call(b, cs.pon_kan_order[cs.pon_kan_idx])
        else:
            b = apply_pass_call(b, kamicha_seat(cs.discard_seat))
    return b


def clear_call_window_state(state: GameState) -> GameState:
    """对 ``GameState`` 的 ``board`` 做 ``clear_call_window``。"""
    b = state.board
    if b is None:
        return state
    nb = clear_call_window(b)
    return GameState(
        phase=state.phase,
        table=state.table,
        board=nb,
        ron_winners=state.ron_winners,
    )
