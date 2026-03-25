"""演示用假数据：牌河与副露，供 ``demo.py`` 等 PNG 演示共用。"""

from __future__ import annotations

from kernel.deal.model import RiverEntry
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile


def sample_river_tiles() -> dict[int, list[Tile]]:
    """四家各 12 张河牌（与旧 demo 内嵌数据一致）。"""
    return {
        0: [
            Tile(Suit.MAN, 1, False),
            Tile(Suit.PIN, 5, True),
            Tile(Suit.SOU, 9, False),
            Tile(Suit.HONOR, 1, False),
            Tile(Suit.MAN, 3, False),
            Tile(Suit.PIN, 7, False),
            Tile(Suit.SOU, 3, False),
            Tile(Suit.MAN, 5, True),
            Tile(Suit.PIN, 2, False),
            Tile(Suit.HONOR, 7, False),
            Tile(Suit.SOU, 1, False),
            Tile(Suit.MAN, 9, False),
        ],
        1: [
            Tile(Suit.PIN, 1, False),
            Tile(Suit.SOU, 5, True),
            Tile(Suit.MAN, 9, False),
            Tile(Suit.HONOR, 2, False),
            Tile(Suit.PIN, 3, False),
            Tile(Suit.SOU, 7, False),
            Tile(Suit.MAN, 2, False),
            Tile(Suit.PIN, 5, False),
            Tile(Suit.HONOR, 4, False),
            Tile(Suit.SOU, 9, False),
            Tile(Suit.MAN, 4, False),
            Tile(Suit.PIN, 8, False),
        ],
        2: [
            Tile(Suit.SOU, 1, False),
            Tile(Suit.MAN, 5, True),
            Tile(Suit.PIN, 9, False),
            Tile(Suit.HONOR, 3, False),
            Tile(Suit.SOU, 3, False),
            Tile(Suit.MAN, 7, False),
            Tile(Suit.PIN, 4, False),
            Tile(Suit.SOU, 5, False),
            Tile(Suit.HONOR, 5, False),
            Tile(Suit.MAN, 1, False),
            Tile(Suit.PIN, 6, False),
            Tile(Suit.SOU, 8, False),
        ],
        3: [
            Tile(Suit.HONOR, 1, False),
            Tile(Suit.MAN, 5, True),
            Tile(Suit.PIN, 1, False),
            Tile(Suit.SOU, 7, False),
            Tile(Suit.HONOR, 2, False),
            Tile(Suit.MAN, 8, False),
            Tile(Suit.PIN, 3, False),
            Tile(Suit.SOU, 2, False),
            Tile(Suit.HONOR, 6, False),
            Tile(Suit.MAN, 2, False),
            Tile(Suit.PIN, 9, False),
            Tile(Suit.SOU, 4, False),
        ],
    }


def sample_melds() -> dict[int, tuple[Meld, ...]]:
    """四家副露组（与旧 demo 内嵌数据一致）。"""
    return {
        0: (
            Meld(
                kind=MeldKind.PON,
                tiles=(
                    Tile(Suit.MAN, 7, False),
                    Tile(Suit.MAN, 7, False),
                    Tile(Suit.MAN, 7, False),
                ),
                called_tile=Tile(Suit.MAN, 7, False),
                from_seat=3,
            ),
            Meld(
                kind=MeldKind.SHANKUMINKAN,
                tiles=(
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                ),
                called_tile=Tile(Suit.SOU, 6, False),
                from_seat=0,
            ),
        ),
        1: (
            Meld(
                kind=MeldKind.CHI,
                tiles=(
                    Tile(Suit.PIN, 4, False),
                    Tile(Suit.PIN, 5, False),
                    Tile(Suit.PIN, 6, False),
                ),
                called_tile=Tile(Suit.PIN, 6, False),
                from_seat=0,
            ),
            Meld(
                kind=MeldKind.PON,
                tiles=(
                    Tile(Suit.MAN, 7, False),
                    Tile(Suit.MAN, 7, False),
                    Tile(Suit.MAN, 7, False),
                ),
                called_tile=Tile(Suit.MAN, 7, False),
                from_seat=3,
            ),
            Meld(
                kind=MeldKind.SHANKUMINKAN,
                tiles=(
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                ),
                called_tile=Tile(Suit.SOU, 6, False),
                from_seat=1,
            ),
        ),
        2: (
            Meld(
                kind=MeldKind.DAIMINKAN,
                tiles=(
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                    Tile(Suit.SOU, 6, False),
                ),
                called_tile=Tile(Suit.SOU, 6, False),
                from_seat=1,
            ),
        ),
        3: (
            Meld(
                kind=MeldKind.PON,
                tiles=(
                    Tile(Suit.HONOR, 4, False),
                    Tile(Suit.HONOR, 4, False),
                    Tile(Suit.HONOR, 4, False),
                ),
                called_tile=Tile(Suit.HONOR, 4, False),
                from_seat=2,
            ),
        ),
    }


def river_entries_from_sample() -> tuple[RiverEntry, ...]:
    """由 ``sample_river_tiles`` 生成 ``RiverEntry`` 序列（每家 12 张顺序）。"""
    river_tiles = sample_river_tiles()
    entries: list[RiverEntry] = []
    for seat in range(4):
        for i, tile in enumerate(river_tiles[seat]):
            entries.append(RiverEntry(seat=seat, tile=tile, tsumogiri=(i % 3 == 0), riichi=False))
    return tuple(entries)
