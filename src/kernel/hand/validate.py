"""门内 + 副露的张数守恒与组合校验。"""

from __future__ import annotations

from collections import Counter
from typing import Literal, Sequence

from kernel.hand.melds import Meld, meld_tile_count, validate_meld_shape
from kernel.hand.multiset import concealed_total
from kernel.tiles.model import Tile


def tiles_from_concealed_and_melds(
    concealed: Counter[Tile],
    melds: Sequence[Meld],
) -> list[Tile]:
    """展开门内与所有副露中的牌（含副露重复张），供对账或测试。"""
    out: list[Tile] = []
    for t, n in concealed.items():
        out.extend([t] * n)
    for m in melds:
        out.extend(m.tiles)
    return out


def validate_tile_conservation(
    concealed: Counter[Tile],
    melds: Sequence[Meld],
    expected_total: Literal[13, 14],
) -> None:
    """
    校验：门内张数 + 各副露张数之和 == expected_total。
    常见：未摸牌 13；摸进后未打出 14。
    """
    c = concealed_total(concealed)
    m = sum(meld_tile_count(x) for x in melds)
    total = c + m
    if total != expected_total:
        msg = (
            f"tile count mismatch: concealed={c}, melds={m}, sum={total}, expected {expected_total}"
        )
        raise ValueError(msg)


def validate_hand_package(
    concealed: Counter[Tile],
    melds: Sequence[Meld],
    expected_total: Literal[13, 14],
) -> None:
    """先校验各副露形状，再校验张数守恒。"""
    for m in melds:
        validate_meld_shape(m)
    validate_tile_conservation(concealed, melds, expected_total)
