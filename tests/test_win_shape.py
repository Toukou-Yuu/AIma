"""标准形扩展与岭上自摸形判。"""

from __future__ import annotations

from collections import Counter

from kernel.call.win import can_tsumo_default, can_win_seven_pairs_concealed_14
from kernel.tiles.model import Suit, Tile
from kernel.win_shape.std import can_win_standard_form_concealed_total


def test_can_win_standard_form_concealed_total_four_triplets_pair() -> None:
    """111 222 333 444m + 55m = 14 张标准形。"""
    c: Counter[Tile] = Counter()
    for r in (1, 2, 3, 4):
        c[Tile(Suit.MAN, r)] = 3
    c[Tile(Suit.MAN, 5)] = 2
    assert can_win_standard_form_concealed_total(c, ()) is True


def test_can_win_seven_pairs_concealed_14() -> None:
    c = Counter()
    for r in range(1, 8):
        t = Tile(Suit.MAN, r)
        c[t] = 2
    assert can_win_seven_pairs_concealed_14(c, ()) is True
    c[Tile(Suit.MAN, 1)] = 1
    assert can_win_seven_pairs_concealed_14(c, ()) is False


def test_can_tsumo_rinshan_seven_pairs() -> None:
    """15 张：六对 + 刻子 7m，和了牌为 7m。"""
    c = Counter()
    for r in range(1, 7):
        c[Tile(Suit.MAN, r)] = 2
    c[Tile(Suit.MAN, 7)] = 3
    t7 = Tile(Suit.MAN, 7)
    assert can_tsumo_default(c, (), t7, last_draw_was_rinshan=True) is True


def test_can_tsumo_rinshan_rejects_wrong_total() -> None:
    c = Counter()
    for r in range(1, 7):
        c[Tile(Suit.MAN, r)] = 2
    c[Tile(Suit.MAN, 7)] = 2
    assert can_tsumo_default(c, (), Tile(Suit.MAN, 7), last_draw_was_rinshan=True) is False


def test_can_tsumo_non_rinshan_unchanged() -> None:
    """非岭上：门内须为 14 张（含摸入的和了牌），去掉一枚和了牌后与荣和同判。"""
    c = Counter()
    for r in range(1, 8):
        c[Tile(Suit.MAN, r)] = 2
    assert can_tsumo_default(c, (), Tile(Suit.MAN, 7), last_draw_was_rinshan=False) is True
