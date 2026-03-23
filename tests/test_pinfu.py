"""平和役与符（子集）。"""

from __future__ import annotations

from collections import Counter

from kernel.scoring.fu import compute_fu
from kernel.tiles.model import Suit, Tile
from kernel.win_shape.pinfu import pinfu_eligible


def _pinfu_ron_hand_13() -> Counter[Tile]:
    c = Counter()
    for r in range(1, 7):
        c[Tile(Suit.MAN, r)] = 1
    for r in range(1, 6):
        c[Tile(Suit.PIN, r)] = 1
    c[Tile(Suit.SOU, 8)] = 2
    return c


def test_pinfu_eligible_ron_ryanmen() -> None:
    c = _pinfu_ron_hand_13()
    w6p = Tile(Suit.PIN, 6)
    rw = Tile(Suit.HONOR, 1)
    sw = Tile(Suit.HONOR, 2)
    assert pinfu_eligible(c, (), w6p, for_ron=True, round_wind_tile=rw, seat_wind_tile=sw) is True


def test_pinfu_ineligible_yakuhai_pair() -> None:
    c = Counter()
    for r in range(1, 7):
        c[Tile(Suit.MAN, r)] = 1
    for r in range(1, 6):
        c[Tile(Suit.PIN, r)] = 1
    c[Tile(Suit.HONOR, 1)] = 2
    w6p = Tile(Suit.PIN, 6)
    rw = Tile(Suit.HONOR, 1)
    sw = Tile(Suit.HONOR, 1)
    assert pinfu_eligible(c, (), w6p, for_ron=True, round_wind_tile=rw, seat_wind_tile=sw) is False


def test_pinfu_eligible_tsumo_no_ryanmen_gate() -> None:
    """自摸不要求两面待；门内 14 张已含和了牌。"""
    c = Counter()
    for r in range(1, 7):
        c[Tile(Suit.MAN, r)] = 1
    for r in range(1, 7):
        c[Tile(Suit.PIN, r)] = 1
    c[Tile(Suit.SOU, 8)] = 2
    assert sum(c.values()) == 14  # 6+6+2
    w6p = Tile(Suit.PIN, 6)
    rw = Tile(Suit.HONOR, 1)
    sw = Tile(Suit.HONOR, 2)
    assert pinfu_eligible(c, (), w6p, for_ron=False, round_wind_tile=rw, seat_wind_tile=sw) is True


def test_compute_fu_pinfu_branch() -> None:
    assert compute_fu(menzen=True, is_ron=True, pinfu=True) == 30
    assert compute_fu(menzen=True, is_ron=False, pinfu=True) == 20
    assert compute_fu(menzen=True, is_ron=True, pinfu=False) == 40
