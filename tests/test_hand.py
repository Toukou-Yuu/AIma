"""Tests for concealed hand multiset, meld shapes, and tile conservation."""

from __future__ import annotations

import pytest

from kernel import (
    Meld,
    MeldKind,
    Suit,
    Tile,
    add_tile,
    concealed_from_iterable,
    concealed_total,
    remove_tile,
    tiles_from_concealed_and_melds,
    triplet_key,
    validate_hand_package,
    validate_meld_shape,
    validate_tile_conservation,
)


def _m(rank: int, red: bool = False) -> Tile:
    return Tile(Suit.MAN, rank, is_red=red)


def _p(rank: int, red: bool = False) -> Tile:
    return Tile(Suit.PIN, rank, is_red=red)


def _z(rank: int) -> Tile:
    return Tile(Suit.HONOR, rank)


def test_triplet_key_ignores_red_for_numbered() -> None:
    assert triplet_key(_m(5, False)) == triplet_key(_m(5, True))


def test_chi_valid_plain_and_red() -> None:
    t4, t5, t6 = _m(4), _m(5), _m(6)
    m = Meld(MeldKind.CHI, (t4, t5, t6), called_tile=t5)
    validate_meld_shape(m)

    t5r = _m(5, True)
    m2 = Meld(MeldKind.CHI, (t4, t5r, t6), called_tile=t5r)
    validate_meld_shape(m2)


def test_chi_rejects_wrong_order() -> None:
    t4, t5, t6 = _m(4), _m(5), _m(6)
    m = Meld(MeldKind.CHI, (t6, t5, t4), called_tile=t5)
    with pytest.raises(ValueError, match="sorted ascending"):
        validate_meld_shape(m)


def test_chi_rejects_cross_suit() -> None:
    tiles = (_m(4), _m(5), _p(6))
    m = Meld(MeldKind.CHI, tiles, called_tile=tiles[1])
    with pytest.raises(ValueError, match="same suit"):
        validate_meld_shape(m)


def test_chi_rejects_honor() -> None:
    tiles = (_m(4), _m(5), _z(1))
    m = Meld(MeldKind.CHI, tiles, called_tile=tiles[1])
    with pytest.raises(ValueError, match="honor"):
        validate_meld_shape(m)


def test_chi_rejects_non_consecutive() -> None:
    tiles = (_m(4), _m(5), _m(7))
    m = Meld(MeldKind.CHI, tiles, called_tile=tiles[1])
    with pytest.raises(ValueError, match="consecutive"):
        validate_meld_shape(m)


def test_chi_requires_called_in_tiles() -> None:
    t4, t5, t6 = _m(4), _m(5), _m(6)
    m = Meld(MeldKind.CHI, (t4, t5, t6), called_tile=_m(3))
    with pytest.raises(ValueError, match="called_tile"):
        validate_meld_shape(m)


def test_pon_mixed_red() -> None:
    a = _m(5, False)
    b = _m(5, True)
    tiles = (a, a, b)
    m = Meld(MeldKind.PON, tiles, called_tile=b)
    validate_meld_shape(m)


def test_pon_honor() -> None:
    t = _z(3)
    m = Meld(MeldKind.PON, (t, t, t), called_tile=t)
    validate_meld_shape(m)


def test_pon_rejects_mixed_rank() -> None:
    tiles = (_m(4), _m(4), _m(5))
    m = Meld(MeldKind.PON, tiles, called_tile=tiles[0])
    with pytest.raises(ValueError, match="triplet_key"):
        validate_meld_shape(m)


def test_daiminkan_four_same_key() -> None:
    a = _m(5, False)
    b = _m(5, True)
    tiles = (a, a, a, b)
    m = Meld(MeldKind.DAIMINKAN, tiles, called_tile=b)
    validate_meld_shape(m)


def test_ankan_no_called() -> None:
    t = _z(5)
    m = Meld(MeldKind.ANKAN, (t, t, t, t), called_tile=None)
    validate_meld_shape(m)


def test_ankan_rejects_called() -> None:
    t = _z(2)
    m = Meld(MeldKind.ANKAN, (t, t, t, t), called_tile=t)
    with pytest.raises(ValueError, match="called_tile=None"):
        validate_meld_shape(m)


def test_shankuminkan_optional_called() -> None:
    a = _p(5, False)
    b = _p(5, True)
    tiles = (a, a, a, b)
    validate_meld_shape(Meld(MeldKind.SHANKUMINKAN, tiles, called_tile=None))
    validate_meld_shape(Meld(MeldKind.SHANKUMINKAN, tiles, called_tile=b))


def test_shankuminkan_rejects_bad_called() -> None:
    tiles = (_p(3),) * 4
    m = Meld(MeldKind.SHANKUMINKAN, tiles, called_tile=_p(4))
    with pytest.raises(ValueError, match="called_tile"):
        validate_meld_shape(m)


def test_daiminkan_wrong_count() -> None:
    tiles = (_m(1),) * 3
    m = Meld(MeldKind.DAIMINKAN, tiles, called_tile=tiles[0])
    with pytest.raises(ValueError, match="exactly 4"):
        validate_meld_shape(m)


def test_add_remove_tile() -> None:
    t1, t2 = _m(1), _m(2)
    c0 = concealed_from_iterable([t1])
    c1 = add_tile(c0, t2)
    assert concealed_total(c0) == 1
    assert concealed_total(c1) == 2
    c2 = remove_tile(c1, t2)
    assert concealed_total(c2) == 1
    assert c2 == c0


def test_remove_tile_missing_raises() -> None:
    with pytest.raises(ValueError, match="cannot remove"):
        remove_tile(concealed_from_iterable([]), _m(1))


def test_tile_conservation_14_menzen() -> None:
    tiles = [_m(i % 9 + 1) for i in range(14)]
    c = concealed_from_iterable(tiles)
    validate_tile_conservation(c, [], 14)


def test_tile_conservation_13() -> None:
    tiles = [_m(i % 9 + 1) for i in range(13)]
    c = concealed_from_iterable(tiles)
    validate_tile_conservation(c, [], 13)


def test_tile_conservation_with_meld() -> None:
    chi = Meld(MeldKind.CHI, (_m(2), _m(3), _m(4)), called_tile=_m(3))
    concealed = concealed_from_iterable([_m(1)] * 11)
    validate_tile_conservation(concealed, [chi], 14)


def test_tile_conservation_mismatch_raises() -> None:
    chi = Meld(MeldKind.CHI, (_m(2), _m(3), _m(4)), called_tile=_m(3))
    concealed = concealed_from_iterable([_m(1)] * 10)
    with pytest.raises(ValueError, match="mismatch"):
        validate_tile_conservation(concealed, [chi], 14)


def test_validate_hand_package_ok() -> None:
    chi = Meld(MeldKind.CHI, (_m(2), _m(3), _m(4)), called_tile=_m(3))
    concealed = concealed_from_iterable([_m(1)] * 11)
    validate_hand_package(concealed, [chi], 14)


def test_validate_hand_package_invalid_meld_first() -> None:
    bad = Meld(MeldKind.CHI, (_m(2), _m(3), _m(5)), called_tile=_m(3))
    concealed = concealed_from_iterable([_m(1)] * 11)
    with pytest.raises(ValueError, match="consecutive"):
        validate_hand_package(concealed, [bad], 14)


def test_tiles_from_concealed_and_melds() -> None:
    chi = Meld(MeldKind.CHI, (_m(2), _m(3), _m(4)), called_tile=_m(3))
    c = concealed_from_iterable([_m(1), _m(1)])
    flat = tiles_from_concealed_and_melds(c, [chi])
    assert len(flat) == 5
