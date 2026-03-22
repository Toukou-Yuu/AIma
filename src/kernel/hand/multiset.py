"""门内手牌：以 Tile 为键的多重集合（不可变更新风格）。"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from kernel.tiles.model import Tile


def concealed_from_iterable(tiles: Iterable[Tile]) -> Counter[Tile]:
    """由 iterable 构造门内多重集合。"""
    return Counter(tiles)


def concealed_total(concealed: Counter[Tile]) -> int:
    """门内牌总张数。"""
    return sum(concealed.values())


def add_tile(concealed: Counter[Tile], tile: Tile) -> Counter[Tile]:
    """返回拷贝：加入一张牌。"""
    out = concealed.copy()
    out[tile] += 1
    return out


def remove_tile(concealed: Counter[Tile], tile: Tile) -> Counter[Tile]:
    """
    返回拷贝：移除一张牌。
    若该牌计数为 0，抛出 ValueError。
    """
    if concealed.get(tile, 0) <= 0:
        msg = f"cannot remove tile not in hand: {tile!r}"
        raise ValueError(msg)
    out = concealed.copy()
    out[tile] -= 1
    if out[tile] == 0:
        del out[tile]
    return out


def remove_tiles(concealed: Counter[Tile], tiles: Iterable[Tile]) -> Counter[Tile]:
    """依次移除多张牌；任一不足则抛错。"""
    out = concealed
    for t in tiles:
        out = remove_tile(out, t)
    return out
