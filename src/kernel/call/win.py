"""和了形探测（K7 最小子集）；完整役种见后续里程碑。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld
from kernel.tiles.model import Tile


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
