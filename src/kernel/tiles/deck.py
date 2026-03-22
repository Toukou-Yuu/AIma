"""整副牌生成与洗牌。行为对照 mahjong_rules/Mahjong_Soul.md §4（含默认三赤）。"""

from __future__ import annotations

import random
from typing import Sequence

from kernel.tiles.model import Suit, Tile


def build_deck(*, red_fives: bool = True) -> list[Tile]:
    """
    构造无序的 136 张牌。
    ``red_fives=True`` 时：5m/5p/5s 各 3 张普通 + 1 张赤。
    """
    out: list[Tile] = []
    for suit in (Suit.MAN, Suit.PIN, Suit.SOU):
        for rank in range(1, 10):
            if rank == 5 and red_fives:
                # 三赤：各花色 3 普通 + 1 赤
                for _ in range(3):
                    out.append(Tile(suit, 5, False))
                out.append(Tile(suit, 5, True))
            else:
                for _ in range(4):
                    out.append(Tile(suit, rank, False))
    for hr in range(1, 8):
        for _ in range(4):
            out.append(Tile(Suit.HONOR, hr, False))
    if len(out) != 136:
        msg = f"expected 136 tiles, got {len(out)}"
        raise RuntimeError(msg)
    return out


def shuffle_deck(deck: Sequence[Tile], *, seed: int | None = None) -> list[Tile]:
    """
    返回洗牌后的新列表，不修改入参。
    给定相同 ``seed`` 时排列可复现；``seed is None`` 时为非确定性洗牌。
    """
    tiles = list(deck)
    rng = random.Random() if seed is None else random.Random(seed)
    rng.shuffle(tiles)
    return tiles
