"""和了形探测；荣和默认支持七对子与标准四面子一雀头。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, meld_tile_count
from kernel.tiles.model import Tile
from kernel.win_shape.std import can_win_standard_form, can_win_standard_form_concealed_total


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


def can_ron_default(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
) -> bool:
    """默认荣和形：七对子优先，否则标准形。"""
    if can_ron_seven_pairs(concealed, melds, win_tile):
        return True
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
