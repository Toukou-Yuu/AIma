"""标准形（4 面子 + 1 雀头）和了判定；赤五与通常五在顺子/刻子中按同 rank 消耗。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, meld_tile_count
from kernel.tiles.model import Suit, Tile


def tile_to_index(t: Tile) -> int:
    """0..33：万 0–8、筒 9–17、索 18–26、字 27–33（赤五并入对应花色 rank5 槽）。"""
    if t.suit == Suit.HONOR:
        return 27 + (t.rank - 1)
    base = {Suit.MAN: 0, Suit.PIN: 9, Suit.SOU: 18}[t.suit]
    return base + (t.rank - 1)


def concealed_to_vec34(concealed: Counter[Tile]) -> list[int]:
    v = [0] * 34
    for t, n in concealed.items():
        v[tile_to_index(t)] += n
    return v


def _first_nonzero(v: list[int]) -> int | None:
    for i, n in enumerate(v):
        if n:
            return i
    return None


def _can_form_mentsu_only(v: list[int], mentsu_left: int) -> bool:
    """已抽出雀头后，仅用刻子/顺子（无字顺）填满剩余。"""
    if mentsu_left == 0:
        return all(x == 0 for x in v)
    i = _first_nonzero(v)
    if i is None:
        return mentsu_left == 0

    # 刻子
    if v[i] >= 3:
        w = v.copy()
        w[i] -= 3
        if _can_form_mentsu_only(w, mentsu_left - 1):
            return True

    # 顺子（仅数牌）
    if i < 27 and i % 9 <= 6:
        if v[i] >= 1 and v[i + 1] >= 1 and v[i + 2] >= 1:
            w = v.copy()
            w[i] -= 1
            w[i + 1] -= 1
            w[i + 2] -= 1
            if _can_form_mentsu_only(w, mentsu_left - 1):
                return True

    return False


def _can_win_vec34_with_pair(v: list[int], mentsu_needed: int) -> bool:
    """``v`` 为 14 张门内（含和了牌）；需组成 ``mentsu_needed`` 个面子 + 1 雀头。"""
    for j in range(34):
        if v[j] >= 2:
            w = v.copy()
            w[j] -= 2
            if _can_form_mentsu_only(w, mentsu_needed):
                return True
    return False


def can_win_standard_form(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
) -> bool:
    """
    副露 + 门内（含荣和的和了牌）能否构成标准形。
    面子总数须为 4（副露每组算 1 面子，杠亦为 1 组）。
    """
    if len(melds) > 4:
        return False
    c = concealed.copy()
    c[win_tile] += 1
    open_tiles = sum(meld_tile_count(m) for m in melds)
    if sum(c.values()) + open_tiles != 14:
        return False
    mentsu_needed = 4 - len(melds)
    if mentsu_needed < 0:
        return False
    v = concealed_to_vec34(c)
    return _can_win_vec34_with_pair(v, mentsu_needed)


def can_win_standard_form_concealed_total(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
) -> bool:
    """
    门内 + 副露合计恰 14 张时的标准四面子一雀头（不再并入 ``win_tile``）。
    用于岭上自摸等「和了牌已在门内」的形判。
    """
    if len(melds) > 4:
        return False
    open_tiles = sum(meld_tile_count(m) for m in melds)
    if sum(concealed.values()) + open_tiles != 14:
        return False
    mentsu_needed = 4 - len(melds)
    if mentsu_needed < 0:
        return False
    v = concealed_to_vec34(concealed)
    return _can_win_vec34_with_pair(v, mentsu_needed)
