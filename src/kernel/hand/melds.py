"""副露（吃碰杠）数据结构；仅校验形状，不判能否鸣牌或是否听牌。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from kernel.tiles.model import Suit, Tile


class MeldKind(Enum):
    """副露种类。"""

    CHI = "chi"
    PON = "pon"
    DAIMINKAN = "daiminkan"
    ANKAN = "ankan"
    SHANKUMINKAN = "shankuminkan"


def triplet_key(tile: Tile) -> tuple[Suit, int]:
    """
    刻子/杠子用「同种」键：数牌只看 suit+rank，赤五与普通五视为同种。
    字牌为 (HONOR, rank)。
    """
    return (tile.suit, tile.rank)


def _chi_sort_key(tile: Tile) -> tuple[int, int]:
    """吃：升序，同 rank 时非赤在前。"""
    return (tile.rank, 1 if tile.is_red else 0)


def _pon_sort_key(tile: Tile) -> tuple[int, int]:
    """碰/杠：按 rank、再非赤在前。"""
    return (tile.rank, 1 if tile.is_red else 0)


def _is_sorted_chi_tiles(tiles: tuple[Tile, ...]) -> bool:
    return tiles == tuple(sorted(tiles, key=_chi_sort_key))


def _is_sorted_pon_like_tiles(tiles: tuple[Tile, ...]) -> bool:
    return tiles == tuple(sorted(tiles, key=_pon_sort_key))


@dataclass(frozen=True, slots=True)
class Meld:
    """
    一组副露。``tiles`` 为规范升序存储；鸣入牌用 ``called_tile`` 标出（暗杠为 None）。
    ``from_seat`` 预留：他家相对座位，供后续鸣牌流程使用。
    """

    kind: MeldKind
    tiles: tuple[Tile, ...]
    called_tile: Tile | None = None
    from_seat: int | None = None


def validate_meld_shape(meld: Meld) -> None:
    """
    校验副露张数、花色/连续性与存储顺序。
    不校验：是否允许鸣牌、巡目、手中是否真有这些牌。
    """
    kind = meld.kind
    tiles = meld.tiles
    called = meld.called_tile

    if kind == MeldKind.CHI:
        if len(tiles) != 3:
            msg = "chi must have exactly 3 tiles"
            raise ValueError(msg)
        if called is None:
            msg = "chi requires called_tile"
            raise ValueError(msg)
        if called not in tiles:
            msg = "called_tile must be one of chi tiles"
            raise ValueError(msg)
        for t in tiles:
            if t.suit == Suit.HONOR:
                msg = "chi cannot include honor tiles"
                raise ValueError(msg)
        if not _is_sorted_chi_tiles(tiles):
            msg = "chi tiles must be sorted ascending by rank (non-red before red at same rank)"
            raise ValueError(msg)
        s0 = tiles[0].suit
        if not all(t.suit == s0 for t in tiles):
            msg = "chi tiles must share the same suit"
            raise ValueError(msg)
        r0, r1, r2 = (tiles[0].rank, tiles[1].rank, tiles[2].rank)
        if r2 - r0 != 2 or r1 != r0 + 1:
            msg = "chi ranks must be three consecutive numbers"
            raise ValueError(msg)
        return

    if kind == MeldKind.PON:
        if len(tiles) != 3:
            msg = "pon must have exactly 3 tiles"
            raise ValueError(msg)
        if called is None:
            msg = "pon requires called_tile"
            raise ValueError(msg)
        if called not in tiles:
            msg = "called_tile must be one of pon tiles"
            raise ValueError(msg)
        if not _is_sorted_pon_like_tiles(tiles):
            msg = "pon tiles must be sorted by rank, non-red before red"
            raise ValueError(msg)
        k0 = triplet_key(tiles[0])
        if not all(triplet_key(t) == k0 for t in tiles):
            msg = "pon tiles must be the same triplet_key (suit+rank; red 5 matches plain 5)"
            raise ValueError(msg)
        return

    if kind == MeldKind.DAIMINKAN:
        if len(tiles) != 4:
            msg = "daiminkan must have exactly 4 tiles"
            raise ValueError(msg)
        if called is None:
            msg = "daiminkan requires called_tile (the claimed discard)"
            raise ValueError(msg)
        if called not in tiles:
            msg = "called_tile must be one of meld tiles"
            raise ValueError(msg)
        if not _is_sorted_pon_like_tiles(tiles):
            msg = "kan tiles must be sorted by rank, non-red before red"
            raise ValueError(msg)
        k0 = triplet_key(tiles[0])
        if not all(triplet_key(t) == k0 for t in tiles):
            msg = "kan tiles must share the same triplet_key"
            raise ValueError(msg)
        return

    if kind == MeldKind.SHANKUMINKAN:
        if len(tiles) != 4:
            msg = "shankuminkan must have exactly 4 tiles"
            raise ValueError(msg)
        if called is not None and called not in tiles:
            msg = "called_tile must be one of meld tiles when set"
            raise ValueError(msg)
        if not _is_sorted_pon_like_tiles(tiles):
            msg = "kan tiles must be sorted by rank, non-red before red"
            raise ValueError(msg)
        k0 = triplet_key(tiles[0])
        if not all(triplet_key(t) == k0 for t in tiles):
            msg = "kan tiles must share the same triplet_key"
            raise ValueError(msg)
        return

    if kind == MeldKind.ANKAN:
        if len(tiles) != 4:
            msg = "ankan must have exactly 4 tiles"
            raise ValueError(msg)
        if called is not None:
            msg = "ankan must have called_tile=None"
            raise ValueError(msg)
        if not _is_sorted_pon_like_tiles(tiles):
            msg = "ankan tiles must be sorted by rank, non-red before red"
            raise ValueError(msg)
        k0 = triplet_key(tiles[0])
        if not all(triplet_key(t) == k0 for t in tiles):
            msg = "ankan tiles must share the same triplet_key"
            raise ValueError(msg)
        return

    msg = f"unknown meld kind: {kind!r}"
    raise ValueError(msg)


def meld_tile_count(meld: Meld) -> int:
    """副露占用的总张数（与 ``len(meld.tiles)`` 相同，供守恒汇总用）。"""
    return len(meld.tiles)
