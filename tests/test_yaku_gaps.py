"""scoring.yaku 覆盖缺口测试。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, MeldKind
from kernel.scoring.yaku import (
    _count_chi_sequences,
    _has_same_suit_sequences,
    _is_tanyao,
    prevailing_wind_tile,
    _yakuhai_han_triplets,
)
from kernel.table.model import PrevailingWind
from kernel.tiles.model import Suit, Tile

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN4 = Tile(Suit.MAN, 4)
MAN5 = Tile(Suit.MAN, 5)
MAN6 = Tile(Suit.MAN, 6)
MAN7 = Tile(Suit.MAN, 7)
MAN9 = Tile(Suit.MAN, 9)
PIN1 = Tile(Suit.PIN, 1)
PIN2 = Tile(Suit.PIN, 2)
PIN3 = Tile(Suit.PIN, 3)
PIN4 = Tile(Suit.PIN, 4)
PIN5 = Tile(Suit.PIN, 5)
PIN6 = Tile(Suit.PIN, 6)
PIN7 = Tile(Suit.PIN, 7)
PIN9 = Tile(Suit.PIN, 9)
SOU1 = Tile(Suit.SOU, 1)
SOU2 = Tile(Suit.SOU, 2)
SOU3 = Tile(Suit.SOU, 3)
SOU4 = Tile(Suit.SOU, 4)
SOU5 = Tile(Suit.SOU, 5)
SOU6 = Tile(Suit.SOU, 6)
SOU7 = Tile(Suit.SOU, 7)
SOU9 = Tile(Suit.SOU, 9)
HAKU = Tile(Suit.HONOR, 5)
HATSU = Tile(Suit.HONOR, 6)
CHUN = Tile(Suit.HONOR, 7)
TON = Tile(Suit.HONOR, 1)
NAN = Tile(Suit.HONOR, 2)
SHA = Tile(Suit.HONOR, 3)
PEI = Tile(Suit.HONOR, 4)


# --- prevailing_wind_tile ---

class TestPrevailingWindTile:
    def test_east(self) -> None:
        assert prevailing_wind_tile(PrevailingWind.EAST) == TON

    def test_south(self) -> None:
        assert prevailing_wind_tile(PrevailingWind.SOUTH) == NAN


# --- _is_tanyao ---

class TestIsTanyao:
    def test_valid_tanyao(self) -> None:
        full = Counter({MAN2: 2, MAN3: 3, PIN4: 3, SOU5: 2, PIN6: 3})
        assert _is_tanyao(full, allow_open=True, has_melds=False) is True

    def test_honor_tile_rejects(self) -> None:
        full = Counter({MAN2: 2, MAN3: 3, TON: 3, SOU5: 2, PIN6: 3})
        assert _is_tanyao(full, allow_open=True, has_melds=False) is False

    def test_terminal_1_rejects(self) -> None:
        full = Counter({MAN1: 2, MAN3: 3, PIN4: 3, SOU5: 2, PIN6: 3})
        assert _is_tanyao(full, allow_open=True, has_melds=False) is False

    def test_terminal_9_rejects(self) -> None:
        full = Counter({MAN9: 2, MAN3: 3, PIN4: 3, SOU5: 2, PIN6: 3})
        assert _is_tanyao(full, allow_open=True, has_melds=False) is False

    def test_open_not_allowed_with_melds(self) -> None:
        full = Counter({MAN2: 2, MAN3: 3, PIN4: 3, SOU5: 2})
        assert _is_tanyao(full, allow_open=False, has_melds=True) is False

    def test_open_allowed_with_melds(self) -> None:
        full = Counter({MAN2: 2, MAN3: 3, PIN4: 3, SOU5: 2})
        assert _is_tanyao(full, allow_open=True, has_melds=True) is True


# --- _yakuhai_han_triplets ---

class TestYakuhaiHanTriplets:
    def test_round_wind_triplet(self) -> None:
        keys = Counter({(Suit.HONOR, 1): 3, (Suit.MAN, 5): 3})
        assert _yakuhai_han_triplets(keys, round_wind_tile=TON, seat_wind_tile=NAN) == 1

    def test_seat_wind_triplet(self) -> None:
        keys = Counter({(Suit.HONOR, 2): 3, (Suit.MAN, 5): 3})
        assert _yakuhai_han_triplets(keys, round_wind_tile=TON, seat_wind_tile=NAN) == 1

    def test_dragon_triplet(self) -> None:
        keys = Counter({(Suit.HONOR, 5): 3, (Suit.MAN, 5): 3})
        assert _yakuhai_han_triplets(keys, round_wind_tile=TON, seat_wind_tile=NAN) == 1

    def test_all_three_dragons(self) -> None:
        keys = Counter({(Suit.HONOR, 5): 3, (Suit.HONOR, 6): 3, (Suit.HONOR, 7): 3})
        assert _yakuhai_han_triplets(keys, round_wind_tile=TON, seat_wind_tile=NAN) == 3

    def test_round_and_seat_same(self) -> None:
        # 场风==自风时，连风刻子计 2 番
        keys = Counter({(Suit.HONOR, 1): 3})
        assert _yakuhai_han_triplets(keys, round_wind_tile=TON, seat_wind_tile=TON) == 2

    def test_no_yakuhai(self) -> None:
        keys = Counter({(Suit.MAN, 5): 3})
        assert _yakuhai_han_triplets(keys, round_wind_tile=TON, seat_wind_tile=NAN) == 0

    def test_pair_not_enough(self) -> None:
        # 对子不够刻子
        keys = Counter({(Suit.HONOR, 5): 2})
        assert _yakuhai_han_triplets(keys, round_wind_tile=TON, seat_wind_tile=NAN) == 0


# --- _has_same_suit_sequences ---

class TestHasSameSuitSequences:
    def test_honitsu_with_chi(self) -> None:
        chi = Meld(kind=MeldKind.CHI, tiles=(MAN1, MAN2, MAN3), called_tile=MAN1)
        ok, suit = _has_same_suit_sequences((chi,), target=1)
        assert ok is True
        assert suit == Suit.MAN

    def test_not_enough_sequences(self) -> None:
        chi = Meld(kind=MeldKind.CHI, tiles=(MAN1, MAN2, MAN3), called_tile=MAN1)
        ok, _ = _has_same_suit_sequences((chi,), target=2)
        assert ok is False

    def test_no_chi_melds(self) -> None:
        pon = Meld(kind=MeldKind.PON, tiles=(MAN5, MAN5, MAN5), called_tile=MAN5)
        ok, _ = _has_same_suit_sequences((pon,), target=1)
        assert ok is False

    def test_multiple_chi_same_suit(self) -> None:
        chi1 = Meld(kind=MeldKind.CHI, tiles=(MAN1, MAN2, MAN3), called_tile=MAN1)
        chi2 = Meld(kind=MeldKind.CHI, tiles=(MAN4, MAN5, MAN6), called_tile=MAN4)
        ok, suit = _has_same_suit_sequences((chi1, chi2), target=2)
        assert ok is True
        assert suit == Suit.MAN


# --- _count_chi_sequences ---

class TestCountChiSequences:
    def test_count_by_suit(self) -> None:
        chi_m = Meld(kind=MeldKind.CHI, tiles=(MAN1, MAN2, MAN3), called_tile=MAN1)
        chi_p = Meld(kind=MeldKind.CHI, tiles=(PIN4, PIN5, PIN6), called_tile=PIN4)
        pon = Meld(kind=MeldKind.PON, tiles=(SOU5, SOU5, SOU5), called_tile=SOU5)
        counts = _count_chi_sequences(Counter(), (chi_m, chi_p, pon))
        assert counts[Suit.MAN] == 1
        assert counts[Suit.PIN] == 1
        assert counts[Suit.SOU] == 0

    def test_no_chi(self) -> None:
        pon = Meld(kind=MeldKind.PON, tiles=(MAN5, MAN5, MAN5), called_tile=MAN5)
        counts = _count_chi_sequences(Counter(), (pon,))
        assert all(v == 0 for v in counts.values())
