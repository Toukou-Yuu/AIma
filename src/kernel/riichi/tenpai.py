"""听牌判定：七对子与 ``can_ron_default`` 标准形（与荣和子集对齐）。"""

from __future__ import annotations

from collections import Counter

from kernel.call.win import can_ron_default
from kernel.hand.melds import Meld
from kernel.tiles.model import Suit, Tile


def _iter_ron_candidate_tiles() -> tuple[Tile, ...]:
    """荣和/听牌枚举用候选牌（含赤五）。"""
    out: list[Tile] = []
    for suit in (Suit.MAN, Suit.PIN, Suit.SOU):
        for r in range(1, 10):
            out.append(Tile(suit, r))
            if r == 5:
                out.append(Tile(suit, 5, is_red=True))
    for r in range(1, 8):
        out.append(Tile(Suit.HONOR, r))
    return tuple(out)


def is_tenpai_seven_pairs(
    concealed_13: Counter[Tile],
    melds: tuple[Meld, ...],
) -> bool:
    """
    门清、13 张时是否为七对子听牌：恰 7 种牌，其中 6 种对子、1 种单骑待ち。
    """
    if melds:
        return False
    if sum(concealed_13.values()) != 13:
        return False
    if len(concealed_13) != 7:
        return False
    counts = list(concealed_13.values())
    return counts.count(1) == 1 and counts.count(2) == 6


def is_tenpai_default(
    concealed_13: Counter[Tile],
    melds: tuple[Meld, ...],
) -> bool:
    """
    是否听牌：七对子听牌，或存在某张和了牌使 ``can_ron_default`` 为真。
    """
    if is_tenpai_seven_pairs(concealed_13, melds):
        return True
    return any(
        can_ron_default(concealed_13, melds, t) for t in _iter_ron_candidate_tiles()
    )
