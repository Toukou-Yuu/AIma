"""门内暗杠与加杠（升杠）；杠后岭摸由 ``rinshan`` 模块处理。"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from kernel.hand.melds import Meld, MeldKind, triplet_key, validate_meld_shape
from kernel.hand.multiset import remove_tile, remove_tiles
from kernel.kan.rinshan import apply_after_kan_rinshan_draw
from kernel.board import CallResolution, TurnPhase

if TYPE_CHECKING:
    from kernel.board import BoardState


def apply_ankan(board: BoardState, seat: int, meld: Meld) -> BoardState:
    """暗杠：须 ``MUST_DISCARD``、门清四张同种；返回岭摸+翻宝后的状态。

    如果配置允许国士抢暗杠且有玩家国士十三面听牌等待此牌，创建抢杠窗口。
    """
    from kernel.board import BoardState
    from kernel.config import get_default_config
    from kernel.call.win import is_kokushi_thirteen_waits_waiting, get_kokushi_waiting_tiles

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

    # 检查国士无双抢暗杠例外
    config = get_default_config()
    ankan_tile = meld.tiles[0]  # 暗杠的牌（四张相同）

    if config.allow_kokushi_rob_ankan:
        # 遍历其他三家，检查是否有国士十三面听牌等待此牌
        for opponent in range(4):
            if opponent == seat:
                continue
            if is_kokushi_thirteen_waits_waiting(board.hands[opponent], board.melds[opponent]):
                waiting = get_kokushi_waiting_tiles(board.hands[opponent])
                if ankan_tile in waiting:
                    # 创建 chankan 窗口（复用 KAKAN 的机制）
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
                    cs = CallResolution.initial_chankan(seat, ankan_tile)
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

    # 无国士例外：正常岭上摸牌流程
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


def apply_kakan(board: BoardState, seat: int, meld: Meld) -> BoardState:
    """加杠：将已有 ``PON`` 与手牌一张合成 ``KAKAN``。"""
    from kernel.board import BoardState

    validate_meld_shape(meld)
    if meld.kind != MeldKind.KAKAN:
        msg = "apply_kakan requires KAKAN meld"
        raise ValueError(msg)
    if board.turn_phase != TurnPhase.MUST_DISCARD:
        msg = "KAKAN requires MUST_DISCARD"
        raise ValueError(msg)
    if seat != board.current_seat:
        msg = "KAKAN seat must equal current_seat"
        raise ValueError(msg)
    if board.last_draw_was_rinshan:
        msg = "KAKAN not allowed before discarding after rinshan draw"
        raise ValueError(msg)
    if board.call_state is not None:
        msg = "KAKAN not allowed during CALL_RESPONSE"
        raise ValueError(msg)
    if board.riichi[seat]:
        msg = "KAKAN not allowed after riichi (only ANKAN)"
        raise ValueError(msg)
    k_new = triplet_key(meld.tiles[0])
    idx = -1
    for i, m in enumerate(board.melds[seat]):
        if m.kind == MeldKind.PON and triplet_key(m.tiles[0]) == k_new:
            idx = i
            break
    if idx < 0:
        msg = "no matching PON for kakan"
        raise ValueError(msg)
    old_pon = board.melds[seat][idx]
    old_c = Counter(old_pon.tiles)
    new_c = Counter(meld.tiles)
    diff = new_c - old_c
    if sum(diff.values()) != 1:
        msg = "kakan must add exactly one hand tile to PON"
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
