"""hand.melds 副露校验覆盖缺口测试。"""

from __future__ import annotations

from kernel.hand.melds import Meld, MeldKind, validate_meld_shape
from kernel.tiles.model import Suit, Tile

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN4 = Tile(Suit.MAN, 4)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)
SOU5 = Tile(Suit.SOU, 5)
TON = Tile(Suit.HONOR, 1)


# --- CHI validation ---

class TestChiValidation:
    def test_called_is_none(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), None))
            raise AssertionError("expected ValueError for chi without called_tile")
        except ValueError:
            pass

    def test_called_not_in_tiles(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), PIN5))
            raise AssertionError("expected ValueError for called_tile not in chi tiles")
        except ValueError:
            pass


# --- PON validation ---

class TestPonValidation:
    def test_called_is_none(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.PON, (MAN5, MAN5, MAN5), None))
            raise AssertionError("expected ValueError for pon without called_tile")
        except ValueError:
            pass

    def test_called_not_in_tiles(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.PON, (MAN5, MAN5, MAN5), PIN5))
            raise AssertionError("expected ValueError for called_tile not in pon tiles")
        except ValueError:
            pass

    def test_unsorted_tiles(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5))
            # sorted case should pass — test the unsorted explicitly
        except ValueError:
            pass
        # unsorted: red before non-red at same rank
        red5 = Tile(Suit.MAN, 5, is_red=True)
        try:
            validate_meld_shape(Meld(MeldKind.PON, (red5, MAN5, MAN5), MAN5))
            raise AssertionError("expected ValueError for unsorted pon tiles")
        except ValueError:
            pass

    def test_triplet_key_mismatch(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.PON, (MAN5, PIN5, SOU5), MAN5))
            raise AssertionError("expected ValueError for pon triplet_key mismatch")
        except ValueError:
            pass


# --- DAIMINKAN validation ---

class TestDaiminkanValidation:
    def test_called_is_none(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.DAIMINKAN, (MAN5, MAN5, MAN5, MAN5), None))
            raise AssertionError("expected ValueError for daiminkan without called_tile")
        except ValueError:
            pass

    def test_called_not_in_tiles(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.DAIMINKAN, (MAN5, MAN5, MAN5, MAN5), PIN5))
            raise AssertionError("expected ValueError for called_tile not in daiminkan tiles")
        except ValueError:
            pass

    def test_unsorted(self) -> None:
        red5 = Tile(Suit.MAN, 5, is_red=True)
        try:
            validate_meld_shape(Meld(MeldKind.DAIMINKAN, (red5, MAN5, MAN5, MAN5), MAN5))
            raise AssertionError("expected ValueError for unsorted daiminkan tiles")
        except ValueError:
            pass

    def test_triplet_key_mismatch(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.DAIMINKAN, (MAN5, MAN5, PIN5, SOU5), MAN5))
            raise AssertionError("expected ValueError for daiminkan triplet_key mismatch")
        except ValueError:
            pass


# --- SHANKUMINKAN validation ---

class TestShankuminkanValidation:
    def test_called_not_in_tiles(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.SHANKUMINKAN, (MAN5, MAN5, MAN5, MAN5), PIN5))
            raise AssertionError("expected ValueError for shankuminkan called not in tiles")
        except ValueError:
            pass

    def test_triplet_key_mismatch(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.SHANKUMINKAN, (MAN5, MAN5, PIN5, SOU5), MAN5))
            raise AssertionError("expected ValueError for shankuminkan triplet_key mismatch")
        except ValueError:
            pass


# --- ANKAN validation ---

class TestAnkanValidation:
    def test_called_is_not_none(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), MAN5))
            raise AssertionError("expected ValueError for ankan with called_tile")
        except ValueError:
            pass

    def test_unsorted(self) -> None:
        red5 = Tile(Suit.MAN, 5, is_red=True)
        try:
            validate_meld_shape(Meld(MeldKind.ANKAN, (red5, MAN5, MAN5, MAN5)))
            raise AssertionError("expected ValueError for unsorted ankan tiles")
        except ValueError:
            pass

    def test_triplet_key_mismatch(self) -> None:
        try:
            validate_meld_shape(Meld(MeldKind.ANKAN, (MAN5, MAN5, PIN5, SOU5)))
            raise AssertionError("expected ValueError for ankan triplet_key mismatch")
        except ValueError:
            pass


# --- unknown MeldKind ---

class TestUnknownMeldKind:
    def test_unknown_kind(self) -> None:
        """传入非法 kind 值应触发 ValueError。"""
        try:
            fake_meld = Meld.__new__(Meld)
            object.__setattr__(fake_meld, 'kind', "invalid")
            object.__setattr__(fake_meld, 'tiles', (MAN5,))
            object.__setattr__(fake_meld, 'called_tile', None)
            object.__setattr__(fake_meld, 'from_seat', None)
            validate_meld_shape(fake_meld)
            raise AssertionError("expected ValueError for unknown meld kind")
        except ValueError:
            pass
