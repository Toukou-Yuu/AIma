"""门内暗杠与加杠（升杠）；杠后岭摸由 ``rinshan`` 模块处理。"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from kernel.hand.melds import Meld, MeldKind, triplet_key, validate_meld_shape
from kernel.hand.multiset import remove_tile, remove_tiles
from kernel.kan.rinshan import apply_after_kan_rinshan_draw
from kernel.play.model import CallResolution, TurnPhase

if TYPE_CHECKING:
    from kernel.deal.model import BoardState


def apply_ankan(board: BoardState, seat: int, meld: Meld) -> BoardState:
    """暗杠：须 ``MUST_DISCARD``、门清四张同种；返回岭摸+翻宝后的状态。"""
    from kernel.deal.model import BoardState

    validate_meld_shape(meld)
    if meld.kind != MeldKind.ANKAN:
        msg = "apply_ankan requires ANKAN meld"
        raise ValueError(msg)
    if board.turn_phase != TurnPhase.MUST_DISCARD:
        msg = "ANKAN requires MUST_DISCARD"
        raise ValueError(msg)
    if seat != board.current_seat:
        msg = "ANKAN seat must equal current_seat"
        raise ValueError(msg)
    if board.last_draw_was_rinshan:
        msg = "ANKAN not allowed before discarding after rinshan draw"
        raise ValueError(msg)
    if board.call_state is not None:
        msg = "ANKAN not allowed during CALL_RESPONSE"
        raise ValueError(msg)
    new_concealed = remove_tiles(board.hands[seat], meld.tiles)
    new_melds = list(board.melds)
    new_melds[seat] = board.melds[seat] + (meld,)
    intermediate = BoardState(
        hands=tuple(new_concealed if s == seat else board.hands[s] for s in range(4)),
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index,
        dead_wall=board.dead_wall,
        revealed_indicators=board.revealed_indicators,
        current_seat=seat,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=board.river,
        melds=tuple(new_melds),
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=board.rinshan_draw_index,
        call_state=None,
        riichi=board.riichi,
        ippatsu_eligible=board.ippatsu_eligible,
        double_riichi=board.double_riichi,
        all_discards_per_seat=board.all_discards_per_seat,
        called_discard_indices=board.called_discard_indices,
    )
    return apply_after_kan_rinshan_draw(intermediate, seat)


def apply_shankuminkan(board: BoardState, seat: int, meld: Meld) -> BoardState:
    """加杠：将已有 ``PON`` 与手牌一张合成 ``SHANKUMINKAN``。"""
    from kernel.deal.model import BoardState

    validate_meld_shape(meld)
    if meld.kind != MeldKind.SHANKUMINKAN:
        msg = "apply_shankuminkan requires SHANKUMINKAN meld"
        raise ValueError(msg)
    if board.turn_phase != TurnPhase.MUST_DISCARD:
        msg = "SHANKUMINKAN requires MUST_DISCARD"
        raise ValueError(msg)
    if seat != board.current_seat:
        msg = "SHANKUMINKAN seat must equal current_seat"
        raise ValueError(msg)
    if board.last_draw_was_rinshan:
        msg = "SHANKUMINKAN not allowed before discarding after rinshan draw"
        raise ValueError(msg)
    if board.call_state is not None:
        msg = "SHANKUMINKAN not allowed during CALL_RESPONSE"
        raise ValueError(msg)
    if board.riichi[seat]:
        msg = "SHANKUMINKAN not allowed after riichi (only ANKAN)"
        raise ValueError(msg)
    k_new = triplet_key(meld.tiles[0])
    idx = -1
    for i, m in enumerate(board.melds[seat]):
        if m.kind == MeldKind.PON and triplet_key(m.tiles[0]) == k_new:
            idx = i
            break
    if idx < 0:
        msg = "no matching PON for shankuminkan"
        raise ValueError(msg)
    old_pon = board.melds[seat][idx]
    old_c = Counter(old_pon.tiles)
    new_c = Counter(meld.tiles)
    diff = new_c - old_c
    if sum(diff.values()) != 1:
        msg = "shankuminkan must add exactly one hand tile to PON"
        raise ValueError(msg)
    extra = next(iter(diff.elements()))
    new_hand = remove_tile(board.hands[seat], extra)
    melds_list = list(board.melds[seat])
    melds_list.pop(idx)
    melds_list.append(meld)
    new_melds_all = list(board.melds)
    new_melds_all[seat] = tuple(melds_list)
    intermediate = BoardState(
        hands=tuple(new_hand if s == seat else board.hands[s] for s in range(4)),
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index,
        dead_wall=board.dead_wall,
        revealed_indicators=board.revealed_indicators,
        current_seat=seat,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=board.river,
        melds=tuple(new_melds_all),
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=board.rinshan_draw_index,
        call_state=None,
        riichi=board.riichi,
        ippatsu_eligible=board.ippatsu_eligible,
        double_riichi=board.double_riichi,
        all_discards_per_seat=board.all_discards_per_seat,
        called_discard_indices=board.called_discard_indices,
    )
    cs = CallResolution.initial_chankan(seat, extra)
    return BoardState(
        hands=intermediate.hands,
        live_wall=intermediate.live_wall,
        live_draw_index=intermediate.live_draw_index,
        dead_wall=intermediate.dead_wall,
        revealed_indicators=intermediate.revealed_indicators,
        current_seat=seat,
        turn_phase=TurnPhase.CALL_RESPONSE,
        river=intermediate.river,
        melds=intermediate.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=intermediate.rinshan_draw_index,
        call_state=cs,
        riichi=intermediate.riichi,
        ippatsu_eligible=intermediate.ippatsu_eligible,
        double_riichi=intermediate.double_riichi,
        all_discards_per_seat=intermediate.all_discards_per_seat,
        called_discard_indices=intermediate.called_discard_indices,
    )
