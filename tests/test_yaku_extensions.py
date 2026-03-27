"""清一色／混一色／杯口／三色同刻／三杠子等一般役（表驱动）。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import Tile, build_board_after_split, build_deck, split_wall
from kernel.deal.model import BoardState
from kernel.hand.melds import Meld, MeldKind
from kernel.scoring.yaku import (
    _is_sanshoku_doukou,
    non_dora_yaku_han_and_labels,
)
from kernel.table.model import initial_table_snapshot
from kernel.tiles.model import Suit
from kernel.win_shape.decompose import menzen_peikou_level


def _board() -> BoardState:
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=0)


def _chinitsu_menzan_no_suuankou() -> Counter[Tile]:
    """123456789m + 111m + 22m（14 张）：清一色一般形、非四暗刻。"""
    c: Counter[Tile] = Counter()
    for i in range(1, 10):
        c[Tile(Suit.MAN, i)] += 1
    for _ in range(3):
        c[Tile(Suit.MAN, 1)] += 1
    for _ in range(2):
        c[Tile(Suit.MAN, 2)] += 1
    return c


def _iipeikou_only_menzan() -> Counter[Tile]:
    """123456789m + 123m + 11m：一杯口（非二杯口）。"""
    c: Counter[Tile] = Counter()
    for i in range(1, 10):
        c[Tile(Suit.MAN, i)] += 1
    for i in range(1, 4):
        c[Tile(Suit.MAN, i)] += 1
    c[Tile(Suit.MAN, 1)] += 2
    return c


def _mk_daiminkan(t: Tile) -> Meld:
    return Meld(
        kind=MeldKind.DAIMINKAN,
        tiles=(t, t, t, t),
        called_tile=t,
        from_seat=1,
    )


def _mk_ankan(t: Tile) -> Meld:
    return Meld(kind=MeldKind.ANKAN, tiles=(t, t, t, t), called_tile=None, from_seat=None)


@pytest.mark.parametrize(
    "concealed, melds, win_tile, for_ron, expected",
    [
        # 123456789m + 123m + 11m：一杯口
        (
            _iipeikou_only_menzan(),
            (),
            Tile(Suit.MAN, 5),
            False,
            1,
        ),
        # 11223344556677m：二杯口
        (
            Counter(
                {
                    Tile(Suit.MAN, 1): 2,
                    Tile(Suit.MAN, 2): 2,
                    Tile(Suit.MAN, 3): 2,
                    Tile(Suit.MAN, 4): 2,
                    Tile(Suit.MAN, 5): 2,
                    Tile(Suit.MAN, 6): 2,
                    Tile(Suit.MAN, 7): 2,
                }
            ),
            (),
            Tile(Suit.MAN, 7),
            False,
            2,
        ),
    ],
)
def test_menzen_peikou_level_param(
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    for_ron: bool,
    expected: int,
) -> None:
    assert menzen_peikou_level(concealed, melds, win_tile, for_ron=for_ron) == expected


def test_menzen_peikou_level_open_zero() -> None:
    """有副露不计杯口。"""
    c = Counter({Tile(Suit.MAN, 1): 2, Tile(Suit.MAN, 2): 2, Tile(Suit.MAN, 3): 2})
    m = (
        Meld(
            kind=MeldKind.CHI,
            tiles=(Tile(Suit.MAN, 4), Tile(Suit.MAN, 5), Tile(Suit.MAN, 6)),
            called_tile=Tile(Suit.MAN, 5),
            from_seat=1,
        ),
    )
    assert menzen_peikou_level(c, m, Tile(Suit.MAN, 1), for_ron=False) == 0


def test_sanshoku_doukou_helper() -> None:
    """三色同刻：万筒索同 rank 刻（含杠键）。"""
    f = Counter(
        {
            Tile(Suit.MAN, 5): 3,
            Tile(Suit.PIN, 5): 3,
            Tile(Suit.SOU, 5): 3,
            Tile(Suit.HONOR, 1): 2,
        }
    )
    assert _is_sanshoku_doukou(f) is True
    f2 = Counter(
        {
            Tile(Suit.MAN, 5): 3,
            Tile(Suit.PIN, 5): 3,
            Tile(Suit.SOU, 4): 3,
            Tile(Suit.HONOR, 1): 2,
        }
    )
    assert _is_sanshoku_doukou(f2) is False


@pytest.mark.parametrize(
    "name, concealed, melds, win_tile, for_ron, expect_labels, han_min",
    [
        (
            "清一色门清",
            _chinitsu_menzan_no_suuankou(),
            (),
            Tile(Suit.MAN, 5),
            False,
            ("清一色(门清)",),
            6,
        ),
        (
            "一杯口+清一色门清",
            _iipeikou_only_menzan(),
            (),
            Tile(Suit.MAN, 5),
            False,
            ("清一色(门清)", "一杯口"),
            7,
        ),
        (
            "清一色副露",
            Counter(
                {
                    Tile(Suit.MAN, 2): 3,
                    Tile(Suit.MAN, 3): 3,
                    Tile(Suit.MAN, 4): 3,
                    Tile(Suit.MAN, 5): 2,
                }
            ),
            (
                Meld(
                    kind=MeldKind.PON,
                    tiles=(Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1)),
                    called_tile=Tile(Suit.MAN, 1),
                    from_seat=1,
                ),
            ),
            Tile(Suit.MAN, 5),
            False,
            ("清一色",),
            5,
        ),
        (
            "混一色门清",
            Counter(
                {
                    Tile(Suit.MAN, 1): 3,
                    Tile(Suit.MAN, 2): 3,
                    Tile(Suit.MAN, 3): 3,
                    Tile(Suit.HONOR, 5): 2,
                    Tile(Suit.HONOR, 6): 2,
                }
            ),
            (),
            Tile(Suit.HONOR, 6),
            False,
            ("混一色(门清)",),
            3,
        ),
        (
            "三色同刻+对对和",
            Counter(
                {
                    Tile(Suit.PIN, 5): 3,
                    Tile(Suit.SOU, 5): 3,
                    Tile(Suit.MAN, 2): 3,
                    Tile(Suit.HONOR, 1): 2,
                }
            ),
            (
                Meld(
                    kind=MeldKind.PON,
                    tiles=(Tile(Suit.MAN, 5), Tile(Suit.MAN, 5), Tile(Suit.MAN, 5)),
                    called_tile=Tile(Suit.MAN, 5),
                    from_seat=1,
                ),
            ),
            Tile(Suit.HONOR, 1),
            False,
            ("对对和", "三色同刻"),
            4,
        ),
        (
            "三杠子",
            Counter({Tile(Suit.HONOR, 5): 2}),
            (
                _mk_daiminkan(Tile(Suit.MAN, 1)),
                _mk_ankan(Tile(Suit.MAN, 9)),
                _mk_daiminkan(Tile(Suit.PIN, 1)),
            ),
            Tile(Suit.HONOR, 5),
            False,
            ("三杠子",),
            2,
        ),
        (
            "四杠子役满",
            Counter({Tile(Suit.HONOR, 5): 2}),
            (
                _mk_daiminkan(Tile(Suit.MAN, 1)),
                _mk_ankan(Tile(Suit.MAN, 9)),
                _mk_daiminkan(Tile(Suit.PIN, 1)),
                _mk_ankan(Tile(Suit.PIN, 9)),
            ),
            Tile(Suit.HONOR, 5),
            False,
            ("四杠子",),
            13,
        ),
    ],
)
def test_non_dora_labels_table(
    name: str,
    concealed: Counter[Tile],
    melds: tuple[Meld, ...],
    win_tile: Tile,
    for_ron: bool,
    expect_labels: tuple[str, ...],
    han_min: int,
) -> None:
    _ = name
    board = _board()
    table = initial_table_snapshot()
    han, labels = non_dora_yaku_han_and_labels(
        board,
        table,
        0,
        for_ron=for_ron,
        win_tile=win_tile,
        concealed=concealed,
        melds=melds,
        is_tsumo=False,
    )
    assert han >= han_min
    for lb in expect_labels:
        assert lb in labels


def test_iipeikou_label_not_with_open_meld() -> None:
    """副露一般形不出现一杯口标签。"""
    c = Counter(
        {
            Tile(Suit.MAN, 1): 1,
            Tile(Suit.MAN, 2): 1,
            Tile(Suit.MAN, 3): 1,
            Tile(Suit.MAN, 4): 1,
            Tile(Suit.MAN, 5): 1,
            Tile(Suit.MAN, 6): 1,
            Tile(Suit.MAN, 7): 2,
            Tile(Suit.MAN, 8): 2,
        }
    )
    m = (
        Meld(
            kind=MeldKind.CHI,
            tiles=(Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3)),
            called_tile=Tile(Suit.MAN, 2),
            from_seat=1,
        ),
    )
    board = _board()
    table = initial_table_snapshot()
    _, labels = non_dora_yaku_han_and_labels(
        board,
        table,
        0,
        for_ron=False,
        win_tile=Tile(Suit.MAN, 6),
        concealed=c,
        melds=m,
        is_tsumo=False,
    )
    assert "一杯口" not in labels
    assert "二杯口" not in labels
