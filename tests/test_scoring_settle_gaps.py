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
    """_is_hotei 河底判定。"""

    def test_river_count_17_returns_true(self) -> None:
        """某席河中 17 张舍牌应判定为河底。"""
        b0 = board_sorted_deal(dealer=0)
        n = 17
        discards = tuple(
            RiverEntry(seat=0, tile=MAN1, tsumogiri=False, riichi=False)
            for _ in range(n)
        )
        all_disc = list(b0.all_discards_per_seat)
        all_disc[0] = tuple(MAN1 for _ in range(n))
        b = replace(
            b0,
            river=discards,
            all_discards_per_seat=tuple(all_disc),
            live_draw_index=b0.live_draw_index + n,
        )
        assert _is_hotei(b, 0) is True

    def test_river_count_16_returns_false(self) -> None:
        """某席河中 16 张舍牌不应判定为河底。"""
        b0 = board_sorted_deal(dealer=0)
        n = 16
        discards = tuple(
            RiverEntry(seat=0, tile=MAN1, tsumogiri=False, riichi=False)
            for _ in range(n)
        )
        all_disc = list(b0.all_discards_per_seat)
        all_disc[0] = tuple(MAN1 for _ in range(n))
        b = replace(
            b0,
            river=discards,
            all_discards_per_seat=tuple(all_disc),
            live_draw_index=b0.live_draw_index + n,
        )
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
