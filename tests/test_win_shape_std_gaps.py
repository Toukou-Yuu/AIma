"""win_shape.std 覆盖缺口测试：防御性守卫分支。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from kernel.win_shape.std import (
    _can_form_mentsu_only,
    _first_nonzero,
    can_win_standard_form,
    can_win_standard_form_concealed_total,
)

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN4 = Tile(Suit.MAN, 4)
MAN5 = Tile(Suit.MAN, 5)


# --- _first_nonzero ---

class TestFirstNonzero:
    def test_all_zero_returns_none(self) -> None:
        assert _first_nonzero([0] * 34) is None

    def test_first_nonzero(self) -> None:
        v = [0] * 34
        v[5] = 1
        assert _first_nonzero(v) == 5


# --- _can_form_mentsu_only ---

class TestCanFormMentsuOnly:
    def test_all_zero_mentsu_zero(self) -> None:
        assert _can_form_mentsu_only([0] * 34, 0) is True

    def test_all_zero_mentsu_positive(self) -> None:
        """全零但 mentsu_left > 0 → False（L39 分支）。"""
        assert _can_form_mentsu_only([0] * 34, 1) is False


# --- can_win_standard_form ---

class TestCanWinStandardForm:
    def test_too_many_melds(self) -> None:
        """melds > 4 → False（L82 分支）。"""
        melds = tuple(
            Meld(MeldKind.PON, (MAN1, MAN1, MAN1), MAN1) for _ in range(5)
        )
        c = Counter({MAN2: 2})
        assert can_win_standard_form(c, melds, MAN2) is False

    def test_negative_mentsu_needed(self) -> None:
        """melds 导致 mentsu_needed < 0 → False（L90 分支）。"""
        melds = tuple(
            Meld(MeldKind.PON, (MAN1, MAN1, MAN1), MAN1) for _ in range(5)
        )
        c = Counter({MAN2: 2})
        # 5 melds → mentsu_needed = 4 - 5 = -1
        assert can_win_standard_form(c, melds, MAN2) is False


# --- can_win_standard_form_concealed_total ---

class TestCanWinStandardFormConcealedTotal:
    def test_too_many_melds(self) -> None:
        """melds > 4 → False（L104 分支）。"""
        melds = tuple(
            Meld(MeldKind.PON, (MAN1, MAN1, MAN1), MAN1) for _ in range(5)
        )
        c = Counter({MAN2: 2})
        assert can_win_standard_form_concealed_total(c, melds) is False

    def test_wrong_total_tiles(self) -> None:
        """总数 != 14 → False（L107 分支）。"""
        c = Counter({MAN1: 3, MAN2: 3, MAN3: 3, MAN4: 3, MAN5: 2})
        # 3+3+3+3+2 = 14 tiles, no melds → should work
        # Let's make it 13 instead
        c13 = Counter({MAN1: 3, MAN2: 3, MAN3: 3, MAN4: 2, MAN5: 2})
        # 3+3+3+2+2 = 13
        assert can_win_standard_form_concealed_total(c13, ()) is False

    def test_negative_mentsu_needed(self) -> None:
        """melds 导致 mentsu_needed < 0 → False（L110 分支）。"""
        melds = tuple(
            Meld(MeldKind.PON, (MAN1, MAN1, MAN1), MAN1) for _ in range(5)
        )
        c = Counter({MAN2: 2})
        assert can_win_standard_form_concealed_total(c, melds) is False
