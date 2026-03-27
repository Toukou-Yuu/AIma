"""流し満貫点棒：与满贯自摸分摊一致（非每家各付满额）。"""

from __future__ import annotations

from kernel.scoring.points import child_tsumo_payments, nagashi_mangan_payments


def test_nagashi_three_noten_matches_child_tsumo_mangan() -> None:
    """三家未听时与 child_tsumo 满贯（子 8000 / 亲 12000）完全一致。"""
    for honba in (0, 1):
        # 子家和了：亲 4000+本场、子各 2000+本场
        w, d = 3, 0
        noten = frozenset({0, 1, 2})
        full = child_tsumo_payments(w, d, 30, 5, honba)
        nag = nagashi_mangan_payments(w, d, honba, noten)
        assert nag == full
        assert full[w] == 8000 + 300 * honba

        # 亲家和了：三家子各 4000+本场
        w, d = 0, 0
        noten = frozenset({1, 2, 3})
        full_d = child_tsumo_payments(w, d, 30, 5, honba)
        nag_d = nagashi_mangan_payments(w, d, honba, noten)
        assert nag_d == full_d
        assert full_d[w] == 12000 + 300 * honba


def test_nagashi_child_split_not_8000_each() -> None:
    """子流し満貫：未听者支付额不同（非三家各 8000）。"""
    w, d, hb = 3, 0, 0
    noten = frozenset({0, 1, 2})
    nag = nagashi_mangan_payments(w, d, hb, noten)
    assert nag[0] != nag[1]  # 亲家多付
    assert sum(nag[s] for s in range(4)) == 0
    assert nag[0] == -4000 and nag[1] == nag[2] == -2000
