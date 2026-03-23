"""平和：门清四顺子 + 非役牌雀头；荣和须为两面待（待ち 2 种、同花色数牌且 rank 差 3）。"""

from __future__ import annotations

from collections import Counter

from kernel.call.win import can_ron_default
from kernel.hand.melds import Meld, triplet_key
from kernel.tiles.model import Suit, Tile
from kernel.win_shape.std import concealed_to_vec34


def _index_to_rep_tile(idx: int) -> Tile:
    """vec34 下标对应的代表牌（非赤）。"""
    if idx >= 27:
        return Tile(Suit.HONOR, idx - 27 + 1)
    suit = (Suit.MAN, Suit.PIN, Suit.SOU)[idx // 9]
    rank = idx % 9 + 1
    return Tile(suit, rank)


def _is_yakuhai_pair_tile(
    pair_tile: Tile,
    *,
    round_wind_tile: Tile,
    seat_wind_tile: Tile,
) -> bool:
    """雀头是否为役牌（场风/自风/三元；赤五与通常五同键）。"""
    pk = triplet_key(pair_tile)
    if pk == triplet_key(round_wind_tile) or pk == triplet_key(seat_wind_tile):
        return True
    if pair_tile.suit == Suit.HONOR and pair_tile.rank in (5, 6, 7):
        return True
    return False


def _try_fill_sequences_only(v: list[int], mentsu_left: int) -> bool:
    """仅用顺子（无刻子）能否恰好消光。"""
    if mentsu_left == 0:
        return all(x == 0 for x in v)
    i = next((k for k, n in enumerate(v) if n), None)
    if i is None:
        return mentsu_left == 0
    if i >= 27 or i % 9 > 6:
        return False
    if v[i] >= 1 and v[i + 1] >= 1 and v[i + 2] >= 1:
        w = v.copy()
        w[i] -= 1
        w[i + 1] -= 1
        w[i + 2] -= 1
        if _try_fill_sequences_only(w, mentsu_left - 1):
            return True
    return False


def _has_pinfu_decomposition_vec(v: list[int], mentsu_needed: int) -> bool:
    """是否存在：雀头非役牌（由调用方传入风位判断）且余下 ``mentsu_needed`` 面子全为顺子。"""
    for j in range(34):
        if v[j] < 2:
            continue
        w = v.copy()
        w[j] -= 2
        if _try_fill_sequences_only(w, mentsu_needed):
            return True
    return False


def _is_chiitoitsu_14(full: Counter[Tile], melds: tuple[Meld, ...]) -> bool:
    if melds:
        return False
    if sum(full.values()) != 14 or len(full) != 7:
        return False
    return all(n == 2 for n in full.values())


def _full_concealed_for_shape(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> Counter[Tile]:
    c = concealed.copy()
    if for_ron:
        c[win_tile] += 1
    return c


def pinfu_eligible(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
    round_wind_tile: Tile,
    seat_wind_tile: Tile,
) -> bool:
    """
    平和可否：门清、非七对、标准形且存在「四顺子 + 非役牌雀头」分解。
    荣和时额外要求两面待：和了牌候选键恰 2 个、同花色数牌且 rank 差 3。
    """
    if melds:
        return False
    full = _full_concealed_for_shape(concealed, melds, win_tile, for_ron=for_ron)
    if _is_chiitoitsu_14(full, melds):
        return False
    if sum(full.values()) != 14:
        return False
    v = concealed_to_vec34(full)
    mentsu_needed = 4
    ok_shape = False
    for j in range(34):
        if v[j] < 2:
            continue
        pair_rep = _index_to_rep_tile(j)
        if _is_yakuhai_pair_tile(
            pair_rep,
            round_wind_tile=round_wind_tile,
            seat_wind_tile=seat_wind_tile,
        ):
            continue
        w = v.copy()
        w[j] -= 2
        if _try_fill_sequences_only(w, mentsu_needed):
            ok_shape = True
            break
    if not ok_shape:
        return False
    if not for_ron:
        return True
    if not can_ron_default(concealed, melds, win_tile):
        return False
    return _is_ryanmen_ron_wait(concealed, melds, win_tile)


def _iter_ron_candidate_tiles() -> tuple[Tile, ...]:
    """荣和待ち枚举用候选牌（含赤五）。"""
    out: list[Tile] = []
    for suit in (Suit.MAN, Suit.PIN, Suit.SOU):
        for r in range(1, 10):
            out.append(Tile(suit, r))
            if r == 5:
                out.append(Tile(suit, 5, is_red=True))
    for r in range(1, 8):
        out.append(Tile(Suit.HONOR, r))
    return tuple(out)


def _ron_wait_triplet_keys(
    concealed_13: Counter[Tile],
    melds: tuple[Meld, ...],
) -> frozenset[tuple[Suit, int]]:
    keys: set[tuple[Suit, int]] = set()
    for t in _iter_ron_candidate_tiles():
        if can_ron_default(concealed_13, melds, t):
            keys.add(triplet_key(t))
    return frozenset(keys)


def _is_ryanmen_ron_wait(
    concealed_13: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
) -> bool:
    """
    两面待（子集）：待ち键恰 2 个；同花色数牌；rank 相差 3（如 36m）；和了牌键在其中。
    排除单骑/嵌张/边张（仅 1 键）及双碰等「两键但非同序延伸」。
    """
    keys = _ron_wait_triplet_keys(concealed_13, melds)
    wk = triplet_key(win_tile)
    if wk not in keys:
        return False
    if len(keys) != 2:
        return False
    k1, k2 = sorted(keys, key=lambda x: (x[0].value, x[1]))
    s1, r1 = k1
    s2, r2 = k2
    if s1 != s2 or s1 == Suit.HONOR:
        return False
    return abs(r1 - r2) == 3
