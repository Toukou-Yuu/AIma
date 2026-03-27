"""门清标准形分解枚举；用于一杯口／二杯口等需面子结构的役。"""

from __future__ import annotations

from collections import Counter

from kernel.tiles.model import Tile
from kernel.win_shape.std import concealed_to_vec34


def _first_nonzero(v: list[int]) -> int | None:
    for i, n in enumerate(v):
        if n:
            return i
    return None


def _dfs_mentsu(v: list[int], mentsu_left: int) -> list[list[tuple[str, int]]]:
    """
    枚举从 ``v`` 中取出 ``mentsu_left`` 个面子（刻子或顺子）的所有方式。
    面子记为 ``('pon', i)`` 或 ``('chi', i)``，``i`` 为 vec34 下标（顺子为起始下标）。
    """
    if mentsu_left == 0:
        return [[]] if all(x == 0 for x in v) else []
    i = _first_nonzero(v)
    if i is None:
        return []
    out: list[list[tuple[str, int]]] = []
    if v[i] >= 3:
        w = v.copy()
        w[i] -= 3
        for rest in _dfs_mentsu(w, mentsu_left - 1):
            out.append([("pon", i)] + rest)
    if i < 27 and i % 9 <= 6:
        if v[i] >= 1 and v[i + 1] >= 1 and v[i + 2] >= 1:
            w = v.copy()
            w[i] -= 1
            w[i + 1] -= 1
            w[i + 2] -= 1
            for rest in _dfs_mentsu(w, mentsu_left - 1):
                out.append([("chi", i)] + rest)
    return out


def enumerate_menzen_decompositions_vec34(v: list[int]) -> list[list[tuple[str, int]]]:
    """
    门清 14 张（vec34）的所有「4 面子 + 1 雀头」分解；每个元素为 4 个面子 tuple 的列表。
    """
    out: list[list[tuple[str, int]]] = []
    for j in range(34):
        if v[j] >= 2:
            w = v.copy()
            w[j] -= 2
            out.extend(_dfs_mentsu(w, 4))
    return out


def menzen_peikou_level_vec34(v: list[int]) -> int:
    """
    一杯口／二杯口：返回 0=无，1=一杯口，2=二杯口（二杯口优先于重复计一杯口）。

    二杯口：存在分解，使 4 面子均为顺子，且顺子起始下标多重集为
    ``{k:4}``（四组相同顺子）或 ``{a:2, b:2}``（两组一盃口）。
    一盃口：存在分解，某顺子起始下标出现至少 2 次，且不构成二杯口。
    """
    decomps = enumerate_menzen_decompositions_vec34(v)
    if not decomps:
        return 0
    has_ryan = False
    has_ii = False
    for ments in decomps:
        chis = [x[1] for x in ments if x[0] == "chi"]
        if len(chis) != 4:
            continue
        ctr = Counter(chis)
        mv = max(ctr.values())
        if mv >= 4:
            has_ryan = True
            continue
        if len(ctr) == 2 and sorted(ctr.values()) == [2, 2]:
            has_ryan = True
            continue
        if any(c >= 2 for c in ctr.values()):
            has_ii = True
    if has_ryan:
        return 2
    if has_ii:
        return 1
    return 0


def menzen_peikou_level(
    concealed: Counter[Tile],
    melds: tuple[object, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> int:
    """门清且标准形时的一杯口／二杯口等级；有副露或非 14 张则 0。"""
    if len(melds) != 0:
        return 0
    c: Counter[Tile] = concealed.copy()
    if for_ron:
        c[win_tile] += 1
    if sum(c.values()) != 14:
        return 0
    v = concealed_to_vec34(c)
    return menzen_peikou_level_vec34(v)
