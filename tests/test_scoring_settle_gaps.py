"""scoring.settle 覆盖缺口测试。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel.play.model import RiverEntry
from kernel.scoring.settle import _is_hotei, settle_ron_table, settle_tsumo_table
from kernel.table.model import initial_table_snapshot
from kernel.tiles.model import Suit, Tile

from tests.engine_helpers import board_sorted_deal

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)


# ===== _is_hotei =====


class TestIsHotei:
    """_is_hotei 河底判定（本墙已空）。"""

    @staticmethod
    def _mock_board(b0, **overrides):
        """绕过 __post_init__ 验证构造修改后的 BoardState。"""
        import dataclasses as dc
        from kernel.deal.model import BoardState
        b = object.__new__(BoardState)
        for f in dc.fields(b0):
            val = overrides.get(f.name, getattr(b0, f.name))
            object.__setattr__(b, f.name, val)
        return b

    def test_live_wall_exhausted_returns_true(self) -> None:
        """本墙已空（live_draw_index >= len(live_wall)) 应判定为河底。"""
        b0 = board_sorted_deal(dealer=0)
        b = self._mock_board(b0, live_draw_index=len(b0.live_wall))
        assert _is_hotei(b, 0) is True

    def test_live_wall_not_exhausted_returns_false(self) -> None:
        """本墙未空不应判定为河底。"""
        b0 = board_sorted_deal(dealer=0)
        b = self._mock_board(b0, live_draw_index=17)
        assert _is_hotei(b, 0) is False


# ===== settle_ron_table / settle_tsumo_table error guards =====


class TestSettleRonTableErrors:
    """settle_ron_table 错误守卫。"""

    def test_empty_ron_winners_raises(self) -> None:
        b = board_sorted_deal(dealer=0)
        tab = initial_table_snapshot()
        try:
            settle_ron_table(tab, b, ron_winners=(), discard_seat=0, win_tile=MAN1)
            raise AssertionError("expected ValueError for empty ron_winners")
        except ValueError:
            pass

    def test_invalid_winner_seat_raises(self) -> None:
        b = board_sorted_deal(dealer=0)
        tab = initial_table_snapshot()
        try:
            settle_ron_table(tab, b, ron_winners=(5,), discard_seat=0, win_tile=MAN1)
            raise AssertionError("expected ValueError for invalid winner seat")
        except ValueError:
            pass


class TestSettleTsumoTableErrors:
    """settle_tsumo_table 错误守卫。"""

    def test_winner_out_of_range_raises(self) -> None:
        b = board_sorted_deal(dealer=0)
        tab = initial_table_snapshot()
        try:
            settle_tsumo_table(tab, b, winner=5, win_tile=MAN1)
            raise AssertionError("expected ValueError for winner out of range")
        except ValueError:
            pass
