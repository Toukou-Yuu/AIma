"""摸打纯函数：在合法前提下返回新 ``BoardState``。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from kernel.hand.multiset import add_tile, remove_tile
from kernel.board import CallResolution, RiverEntry, TurnPhase
from kernel.tiles.model import Tile

if TYPE_CHECKING:
    from kernel.board import BoardState


def apply_draw(board: BoardState, seat: int) -> BoardState:
    """自摸：``NEED_DRAW`` 且 ``seat == current_seat``；墙枯则抛 ``ValueError``。"""
    from kernel.board import BoardState

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
        melds=board.melds,
        last_draw_tile=tile,
        last_draw_was_rinshan=False,
        rinshan_draw_index=board.rinshan_draw_index,
        call_state=None,
        riichi=board.riichi,
        ippatsu_eligible=board.ippatsu_eligible,
        double_riichi=board.double_riichi,
        all_discards_per_seat=board.all_discards_per_seat,
        called_discard_indices=board.called_discard_indices,
    )


def board_after_tsumo_win(board: BoardState, *, winner: int, win_tile: Tile) -> BoardState:
    """
    自摸进入结算占位：转 ``NEED_DRAW``，清摸打标记。
    门内减一枚和了牌并写入河（摸切标记），保持 136 张守恒与各家 13 张（结算谱面占位）。
    """
    from kernel.board import BoardState

    new_hands = list(board.hands)
    new_hands[winner] = remove_tile(new_hands[winner], win_tile)
    new_river = board.river + (
        RiverEntry(seat=winner, tile=win_tile, tsumogiri=True, riichi=False),
    )
    return BoardState(
        hands=tuple(new_hands),
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index,
        dead_wall=board.dead_wall,
        revealed_indicators=board.revealed_indicators,
        current_seat=board.current_seat,
        turn_phase=TurnPhase.NEED_DRAW,
        river=new_river,
        melds=board.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=board.rinshan_draw_index,
        call_state=None,
        riichi=board.riichi,
        ippatsu_eligible=frozenset(),
        double_riichi=board.double_riichi,
        all_discards_per_seat=board.all_discards_per_seat,
        called_discard_indices=board.called_discard_indices,
    )


def apply_discard(
    board: BoardState,
    seat: int,
    tile: Tile,
    *,
    declare_riichi: bool = False,
) -> BoardState:
    """打牌：``MUST_DISCARD``；写入河，下家为下一摸席并进入 ``CALL_RESPONSE``。"""
    from kernel.board import BoardState

    if board.turn_phase != TurnPhase.MUST_DISCARD:
        msg = "DISCARD requires turn_phase MUST_DISCARD"
        raise ValueError(msg)
    if seat != board.current_seat:
        msg = "DISCARD seat must equal current_seat"
        raise ValueError(msg)
    if declare_riichi and board.riichi[seat]:
        msg = "cannot declare riichi when already riichi"
        raise ValueError(msg)
    if board.riichi[seat]:
        if board.last_draw_tile is None or tile != board.last_draw_tile:
            msg = "riichi player must discard the tile just drawn (tsumogiri)"
            raise ValueError(msg)
    tsumogiri = board.last_draw_tile is not None and tile == board.last_draw_tile
    new_hands = list(board.hands)
    new_hands[seat] = remove_tile(new_hands[seat], tile)
    new_discards = list(board.all_discards_per_seat)
    new_discards[seat] = board.all_discards_per_seat[seat] + (tile,)
    entry = RiverEntry(seat=seat, tile=tile, tsumogiri=tsumogiri, riichi=declare_riichi)
    new_river = board.river + (entry,)
    river_index = len(new_river) - 1
    next_seat = (seat + 1) % 4
    # H-04/H-06: Pending riichi + ippatsu expiration
    new_pending_riichi = board.pending_riichi
    new_pending_riichi_tile = board.pending_riichi_tile
    new_ippatsu = board.ippatsu_eligible

    if declare_riichi:
        # H-04: Mark as pending, do NOT finalize here
        new_pending_riichi = seat
        new_pending_riichi_tile = tile
        # Keep riichi, ippatsu, double unchanged (pending state)
    elif board.riichi[seat] and seat in board.ippatsu_eligible:
        # H-06: Already-riichi player discards - ippatsu expires
        new_ippatsu = frozenset(board.ippatsu_eligible - {seat})
    return BoardState(
        hands=tuple(new_hands),
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index,
        dead_wall=board.dead_wall,
        revealed_indicators=board.revealed_indicators,
        current_seat=next_seat,
        turn_phase=TurnPhase.CALL_RESPONSE,
        river=new_river,
        melds=board.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=board.rinshan_draw_index,
        call_state=CallResolution.initial_after_discard(seat, river_index, tile),
        riichi=board.riichi,
        ippatsu_eligible=new_ippatsu,
        double_riichi=board.double_riichi,
        all_discards_per_seat=tuple(new_discards),
        called_discard_indices=board.called_discard_indices,
        pending_riichi=new_pending_riichi,
        pending_riichi_tile=new_pending_riichi_tile,
    )


def finalize_pending_riichi(board: BoardState) -> BoardState:
    """
    Finalize pending riichi declaration after CALL_RESPONSE ends without ron.

    Applies:
    - riichi[seat] = True
    - ippatsu_eligible |= {seat}
    - double_riichi |= {seat} if first discard
    - pending_riichi = None

    Returns: new BoardState with riichi finalized
    """
    if board.pending_riichi is None:
        return board

    seat = board.pending_riichi
    nr = list(board.riichi)
    nr[seat] = True
    new_riichi = tuple(nr)

    new_ippatsu = frozenset(board.ippatsu_eligible | {seat})

    new_double = board.double_riichi
    if not any(e.seat == seat for e in board.river):
        new_double = frozenset(board.double_riichi | {seat})

    return replace(
        board,
        riichi=new_riichi,
        ippatsu_eligible=new_ippatsu,
        double_riichi=new_double,
        pending_riichi=None,
        pending_riichi_tile=None,
    )
