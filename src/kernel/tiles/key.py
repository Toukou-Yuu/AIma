"""逻辑牌种工具：赤五与普通五归一化。

TileKey = (Suit, int) 用于规则判断，忽略 is_red 字段。
"""

from __future__ import annotations

from collections import Counter

from kernel.tiles.model import Suit, Tile

TileKey = tuple[Suit, int]


def tile_key(t: Tile) -> TileKey:
    """逻辑牌种键：忽略赤五身份。

    与 triplet_key 等价，但定义在 tiles 模块便于导入。
    """
    return (t.suit, t.rank)


def logical_counter(counter: Counter[Tile]) -> Counter[TileKey]:
    """将 Counter[Tile] 转为 Counter[TileKey]，赤五与普通五合并。

    Args:
        counter: 原始牌张计数（可能包含赤五）

    Returns:
        逻辑牌种计数（赤五与普通五合并为同一种）
    """
    out: Counter[TileKey] = Counter()
    for t, n in counter.items():
        out[tile_key(t)] += n
    return out