"""摸打纯函数：在合法前提下返回新 ``BoardState``。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.hand.multiset import add_tile, remove_tile
from kernel.play.model import RiverEntry, TurnPhase
from kernel.tiles.model import Tile

if TYPE_CHECKING:
    from kernel.deal.model import BoardState


def apply_draw(board: BoardState, seat: int) -> BoardState:
    """自摸：``NEED_DRAW`` 且 ``seat == current_seat``；墙枯则抛 ``ValueError``。"""
    from kernel.deal.model import BoardState

    if board.turn_phase != TurnPhase.NEED_DRAW:
        msg = "DRAW requires turn_phase NEED_DRAW"
        raise ValueError(msg)
    if seat != board.current_seat:
        msg = "DRAW seat must equal current_seat"
        raise ValueError(msg)
    if board.live_draw_index >= len(board.live_wall):
        msg = "live wall exhausted"
        raise ValueError(msg)
    tile = board.live_wall[board.live_draw_index]
    new_hands = list(board.hands)
    new_hands[seat] = add_tile(new_hands[seat], tile)
    return BoardState(
        hands=tuple(new_hands),
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index + 1,
        dead_wall=board.dead_wall,
        revealed_indicators=board.revealed_indicators,
        current_seat=seat,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=board.river,
        last_draw_tile=tile,
    )


def apply_discard(board: BoardState, seat: int, tile: Tile) -> BoardState:
    """打牌：``MUST_DISCARD``；写入河，轮转下家并进入 ``NEED_DRAW``。"""
    from kernel.deal.model import BoardState

    if board.turn_phase != TurnPhase.MUST_DISCARD:
        msg = "DISCARD requires turn_phase MUST_DISCARD"
        raise ValueError(msg)
    if seat != board.current_seat:
        msg = "DISCARD seat must equal current_seat"
        raise ValueError(msg)
    tsumogiri = board.last_draw_tile is not None and tile == board.last_draw_tile
    new_hands = list(board.hands)
    new_hands[seat] = remove_tile(new_hands[seat], tile)
    entry = RiverEntry(seat=seat, tile=tile, tsumogiri=tsumogiri)
    next_seat = (seat + 1) % 4
    return BoardState(
        hands=tuple(new_hands),
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index,
        dead_wall=board.dead_wall,
        revealed_indicators=board.revealed_indicators,
        current_seat=next_seat,
        turn_phase=TurnPhase.NEED_DRAW,
        river=board.river + (entry,),
        last_draw_tile=None,
    )
