"""门内暗杠与加杠（升杠）；杠后岭摸由 ``rinshan`` 模块处理。"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from kernel.hand.melds import Meld, MeldKind, triplet_key, validate_meld_shape
from kernel.hand.multiset import remove_tile, remove_tiles
from kernel.kan.rinshan import apply_after_kan_rinshan_draw
from kernel.board import CallResolution, TurnPhase
from kernel.tiles.key import tile_key  # P0-1: 用于幺九牌判断

if TYPE_CHECKING:
    from kernel.board import BoardState


# P0-1: 幺九牌集合（使用 Suit 枚举形式，与 logical_counter 返回的 key 一致）
from kernel.tiles.model import Suit
_YAOCHU_KEYS = frozenset([
    (Suit.MAN, 1), (Suit.MAN, 9),  # MAN 1, 9
    (Suit.PIN, 1), (Suit.PIN, 9),  # PIN 1, 9
    (Suit.SOU, 1), (Suit.SOU, 9),  # SOU 1, 9
    (Suit.HONOR, 1), (Suit.HONOR, 2), (Suit.HONOR, 3), (Suit.HONOR, 4),  # 东东南南西西北北
    (Suit.HONOR, 5), (Suit.HONOR, 6), (Suit.HONOR, 7),  # 白发中
])


def _is_kokushi_tenpai(concealed: Counter, melds: tuple[Meld, ...]) -> bool:
    """P0-1: 判断是否为国士无双听牌（十三面或单骑）。

    十三面：13 种幺九牌各 1 张 = 13 张，等待任意一种成对
    单骑：11 种幺九牌各 1 张 + 某种幺九牌 2 张 = 13 张，等待缺失的第 13 种

    Returns True if this is kokushi tenpai (any form).
    """
    if melds:
        for m in melds:
            if m.kind != MeldKind.ANKAN:
                return False  # 非门清

    if sum(concealed.values()) != 13:
        return False

    # 使用 logical_counter（返回的键已经是 TileKey tuple）
    from kernel.tiles.key import logical_counter
    logical = logical_counter(concealed)

    # 统计幺九牌分布（logical 的键已经是 tuple，直接用）
    yaochu_counts = {}
    non_yaochu_count = 0
    for key, cnt in logical.items():
        # key 已经是 (suit, rank) tuple
        if key in _YAOCHU_KEYS:
            yaochu_counts[key] = cnt
        else:
            non_yaochu_count += cnt

    # 国士听牌条件：没有非幺九牌
    if non_yaochu_count > 0:
        return False

    # 十三面：13 种幺九牌各恰好 1 张
    if len(yaochu_counts) == 13 and all(c == 1 for c in yaochu_counts.values()):
        return True

    # 单骑：12 种幺九牌，其中 11 种各 1 张，1 种 2 张
    if len(yaochu_counts) == 12:
        pair_count = sum(1 for c in yaochu_counts.values() if c == 2)
        single_count = sum(1 for c in yaochu_counts.values() if c == 1)
        if pair_count == 1 and single_count == 11:
            return True

    return False


def _get_kokushi_waiting_tiles(concealed: Counter) -> frozenset:
    """P0-1: 获取国士听牌的等待牌。

    十三面：返回空集（等待任意一种，但暗杠牌不在等待列表中）
    单骑：返回缺失的第 13 种幺九牌

    Returns frozenset of tile keys (not Tile objects).
    """
    from kernel.tiles.key import logical_counter

    logical = logical_counter(concealed)

    # 统计幺九牌分布（logical 的键已经是 tuple）
    yaochu_counts = {}
    for key, cnt in logical.items():
        if key in _YAOCHU_KEYS:
            yaochu_counts[key] = cnt

    # 十三面：等待任意一种成对，返回空集（实际实现中暗杠检查会特殊处理）
    if len(yaochu_counts) == 13 and all(c == 1 for c in yaochu_counts.values()):
        return frozenset()  # 十三面等待任意一种，但暗杠牌不在手牌中不可能抢

    # 单骑：返回缺失的第 13 种
    missing = frozenset(k for k in _YAOCHU_KEYS if k not in yaochu_counts)
    return missing


def apply_ankan(board: BoardState, seat: int, meld: Meld) -> BoardState:
    """暗杠：须 ``MUST_DISCARD``、门清四张同种；返回岭摸+翻宝后的状态。

    如果配置允许国士抢暗杠且有玩家国士听牌等待此牌，创建抢杠窗口。
    P0-1: 支持所有国士听牌（十三面和单骑）抢暗杠。
    """
    from kernel.board import BoardState
    from kernel.config import get_default_config
    from kernel.tiles.key import tile_key

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
    ankan_key = tile_key(ankan_tile)

    if config.allow_kokushi_rob_ankan:
        # P0-1: 遍历其他三家，检查是否有国士听牌等待此牌
        for opponent in range(4):
            if opponent == seat:
                continue
            if _is_kokushi_tenpai(board.hands[opponent], board.melds[opponent]):
                waiting_keys = _get_kokushi_waiting_tiles(board.hands[opponent])
                if ankan_key in waiting_keys:
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
                        temporary_furiten=board.temporary_furiten,
                        riichi_furiten=board.riichi_furiten,
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
                        temporary_furiten=intermediate.temporary_furiten,
                        riichi_furiten=intermediate.riichi_furiten,
                    )

    # 无国士例外：检查四杠流局条件
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
        temporary_furiten=board.temporary_furiten,
        riichi_furiten=board.riichi_furiten,
    )

    # 四杠流局检测：在岭上摸牌前检查
    # 如果开杠后总计 4 杠且分散在不同玩家，触发四杠散了流局
    # 此时不应岭上摸牌和翻开指示牌
    from kernel.flow.transitions import is_four_kans_flow
    kan_counts = tuple(
        sum(1 for m in seat_melds if m.kind in (MeldKind.ANKAN, MeldKind.DAIMINKAN, MeldKind.KAKAN))
        for seat_melds in intermediate.melds
    )
    if is_four_kans_flow(kan_counts):
        # 四杠散了：直接返回 intermediate，不岭上摸牌
        # apply.py 会检测并触发流局
        return intermediate

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
        temporary_furiten=board.temporary_furiten,
        riichi_furiten=board.riichi_furiten,
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
        temporary_furiten=intermediate.temporary_furiten,
        riichi_furiten=intermediate.riichi_furiten,
    )
