"""根据局面判断当前应由哪些 seat 决策（顺序为 seat 号升序）。"""

from __future__ import annotations

from kernel import GamePhase, legal_actions
from kernel.deal.model import TurnPhase
from kernel.engine.state import GameState


def pending_actor_seats(state: GameState) -> list[int]:
    """
    返回当前需要提交 ``apply`` 的 seat 列表。

    ``HAND_OVER`` / ``FLOWN`` / ``MATCH_END`` 返回空列表（由 ``runner`` 另处理局间 ``NOOP``）。
    """
    if state.phase == GamePhase.MATCH_END:
        return []
    if state.phase in (GamePhase.HAND_OVER, GamePhase.FLOWN):
        return []
    if state.phase != GamePhase.IN_ROUND or state.board is None:
        return []

    b = state.board
    if b.turn_phase == TurnPhase.CALL_RESPONSE:
        return sorted(s for s in range(4) if legal_actions(state, s))
    if b.turn_phase == TurnPhase.NEED_DRAW:
        return [b.current_seat]
    if b.turn_phase == TurnPhase.MUST_DISCARD:
        return [b.current_seat]
    return []
