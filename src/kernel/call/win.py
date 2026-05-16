"""和了形探测；荣和默认支持国士无双、七对子与标准四面子一雀头。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, meld_tile_count
from kernel.tiles.model import Suit, Tile
from kernel.win_shape.std import can_win_standard_form, can_win_standard_form_concealed_total


# 十三种幺九牌常量
_YAOCHU_TILES: tuple[Tile, ...] = (
    Tile(Suit.MAN, 1),
    Tile(Suit.MAN, 9),
    Tile(Suit.PIN, 1),
    Tile(Suit.PIN, 9),
    Tile(Suit.SOU, 1),
    Tile(Suit.SOU, 9),
    Tile(Suit.HONOR, 1),
    Tile(Suit.HONOR, 2),
    Tile(Suit.HONOR, 3),
    Tile(Suit.HONOR, 4),
    Tile(Suit.HONOR, 5),
    Tile(Suit.HONOR, 6),
    Tile(Suit.HONOR, 7),
)


def _is_yaochu(tile: Tile) -> bool:
    """判断牌是否为幺九牌（老幺或字牌）。"""
    return tile in _YAOCHU_TILES


def _seat_concealed_plus_meld_tiles(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
) -> int:
    return sum(concealed.values()) + sum(meld_tile_count(m) for m in melds)


def can_ron_seven_pairs(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
) -> bool:
    """
    门清七对子荣和：副露须为空，手牌 13 张 + 和了牌 = 14 张且为七对。
    """
    if len(melds) > 0:
        return False
    c = concealed.copy()
    c[win_tile] += 1
    if sum(c.values()) != 14:
        return False
    if len(c) != 7:
        return False
    return all(n == 2 for n in c.values())


def can_win_seven_pairs_concealed_14(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
) -> bool:
    """门内+副露合计 14 张时的七对和了（无副露）。"""
    if melds:
        return False
    if sum(concealed.values()) != 14:
        return False
    if len(concealed) != 7:
        return False
    return all(n == 2 for n in concealed.values())


def _can_ron_kokushi(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
) -> bool:
    """
    国士无双荣和判定。

    十三面听牌：13 种幺九牌各 1 张，荣和任意幺九牌成立。
    十二面听牌：12 种幺九牌各 1 张 + 缺失的那种有 2 张，荣和缺失的那种成立。
    """
    # 门前清限定
    if melds:
        return False

    # 必须有 13 张手牌
    if sum(concealed.values()) != 13:
        return False

    # 荣和牌必须是幺九牌
    if not _is_yaochu(win_tile):
        return False

    # 手牌必须全是幺九牌
    for tile in concealed:
        if not _is_yaochu(tile):
            return False

    # 构造完整手牌（concealed + win_tile）
    full_hand = concealed.copy()
    full_hand[win_tile] += 1

    # 检查是否形成国士无双完成形：
    # - 必须有恰好 13 种牌（所有幺九牌）
    # - 必须有恰好一种牌是 2 张（对子），其他都是 1 张
    if len(full_hand) != 13:
        return False

    # 检查是否包含所有 13 种幺九牌
    for yaochu in _YAOCHU_TILES:
        if full_hand.get(yaochu, 0) < 1:
            return False

    # 检查是否恰好一种牌有 2 张（对子）
    pair_count = sum(1 for count in full_hand.values() if count == 2)
    single_count = sum(1 for count in full_hand.values() if count == 1)

    return pair_count == 1 and single_count == 12


def can_ron_default(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
) -> bool:
    """默认荣和形：国士无双优先，其次七对子，最后标准形。"""
    # 1. 国士无双（最高优先级）
    if _can_ron_kokushi(concealed, melds, win_tile):
        return True
    # 2. 七对子
    if can_ron_seven_pairs(concealed, melds, win_tile):
        return True
    # 3. 标准形
    return can_win_standard_form(concealed, melds, win_tile)


def can_tsumo_default(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    last_draw_was_rinshan: bool,
) -> bool:
    """
    自摸和了：和了牌须在门内且须为上一张自摸（由引擎校验 ``last_draw_tile``）。
    非岭上：门内+副露 14 张，按「去掉一枚和了牌 → 与荣和同判」。
    岭上：门内+副露 15 张，去掉一枚和了牌后若为 14 张，则七对或标准形（门内合计）。
    """
    if concealed.get(win_tile, 0) < 1:
        return False
    if not last_draw_was_rinshan:
        c13 = concealed.copy()
        c13[win_tile] -= 1
        return can_ron_default(c13, melds, win_tile)
    if _seat_concealed_plus_meld_tiles(concealed, melds) != 15:
        return False
    c14 = concealed.copy()
    c14[win_tile] -= 1
    if _seat_concealed_plus_meld_tiles(c14, melds) != 14:
        return False
    if can_win_seven_pairs_concealed_14(c14, melds):
        return True
    return can_win_standard_form_concealed_total(c14, melds)
