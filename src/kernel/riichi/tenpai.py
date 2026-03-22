"""听牌判定（当前与荣和子集对齐：门清七对子）。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld
from kernel.tiles.model import Tile


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
