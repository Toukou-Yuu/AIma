"""表宝牌：指示牌的下一张循环；与手牌（含副露）匹配计数。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, meld_tile_count
from kernel.tiles.model import Suit, Tile
from kernel.wall.split import DeadWall


def successor_tile(t: Tile) -> Tile:
    """宝牌指示的「表宝」：数牌循环 9→1，字牌 北→东（7→1）。"""
    if t.suit == Suit.HONOR:
        nr = 1 if t.rank == 7 else t.rank + 1
        return Tile(Suit.HONOR, nr)
    nr = 1 if t.rank == 9 else t.rank + 1
    return Tile(t.suit, nr, is_red=False)


def dora_from_indicators(revealed: tuple[Tile, ...]) -> tuple[Tile, ...]:
    """每张表指示牌对应一枚表宝牌。"""
    return tuple(successor_tile(x) for x in revealed)


def ura_indicators_for_settlement(
    dead: DeadWall,
    revealed_table_count: int,
) -> tuple[Tile, ...]:
    """
    与当前已翻开表宝指示牌**同数目**的里宝指示牌（``ura_bases[0..k-1]``）。
    仅在和了结算时由引擎传入 ``settle_*``；是否计番仍由 ``board.riichi[winner]`` 决定。
    """
    if revealed_table_count <= 0:
        return ()
    k = min(revealed_table_count, len(dead.ura_bases))
    return tuple(dead.ura_bases[i] for i in range(k))


def count_dora_in_tiles(tiles: Counter[Tile], dora: tuple[Tile, ...]) -> int:
    """``tiles`` 中含多少枚与 ``dora`` 列表匹配的牌（按 ``Tile`` 值；赤五与通常五区分）。"""
    n = 0
    for d in dora:
        n += tiles.get(d, 0)
    return n


def all_winning_tiles_counter(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
) -> Counter[Tile]:
    """荣和：和了牌不在门内计数中，须并入；自摸：和了牌已在门内。"""
    c = concealed.copy()
    if for_ron:
        c[win_tile] += 1
    return c


def melds_tile_counter(melds: tuple[Meld, ...]) -> Counter[Tile]:
    out: Counter[Tile] = Counter()
    for m in melds:
        for t in m.tiles:
            out[t] += 1
    return out


def count_dora_total(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
    revealed_indicators: tuple[Tile, ...],
) -> int:
    dora = dora_from_indicators(revealed_indicators)
    c = all_winning_tiles_counter(concealed, melds, win_tile, for_ron=for_ron)
    c.update(melds_tile_counter(melds))
    return count_dora_in_tiles(c, dora)


def count_ura_dora_total(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    *,
    for_ron: bool,
    ura_indicators: tuple[Tile, ...],
) -> int:
    """里宝：与表宝同规则，指示来自里侧翻开列（由结算传入）。"""
    if not ura_indicators:
        return 0
    dora = dora_from_indicators(ura_indicators)
    c = all_winning_tiles_counter(concealed, melds, win_tile, for_ron=for_ron)
    c.update(melds_tile_counter(melds))
    return count_dora_in_tiles(c, dora)
