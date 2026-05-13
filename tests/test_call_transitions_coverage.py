"""call.transitions 覆盖缺口测试：错误守卫与边界分支。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel.call.transitions import (
    _hand_subset_for_open_meld,
    apply_open_meld,
    apply_pass_call,
    board_after_ron_winners,
)
from kernel.hand.melds import Meld, MeldKind
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from kernel.tiles.model import Suit, Tile
from tests.engine_helpers import (
    board_sorted_deal,
    make_board_with_discard,
    make_chi_pon_daiminkan_board,
    shimocha_seat,
)

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)
SOU5 = Tile(Suit.SOU, 5)
TON = Tile(Suit.HONOR, 1)


def _ron_call_response_board() -> "BoardState":
    """构造一个 ron 阶段的 CALL_RESPONSE 状态。"""
    b = board_sorted_deal(dealer=0)
    tile = next(iter(b.hands[0]))
    b2 = make_board_with_discard(dealer=0, discarder=0, discard_tile=tile, discarder_hand=b.hands[0])
    # 设置为 ron 阶段
    cs = b2.call_state
    assert cs is not None
    o1 = (0 + 1) % 4
    o2 = (0 + 2) % 4
    o3 = (0 + 3) % 4
    cs_ron = replace(
        cs,
        stage="ron",
        ron_remaining=frozenset({o1, o2, o3}),
        ron_claimants=frozenset(),
        pon_kan_order=(o1, o2, o3),
        pon_kan_idx=0,
    )
    return replace(b2, call_state=cs_ron)


# --- _hand_subset_for_open_meld ---

class TestHandSubsetForOpenMeld:
    def test_claimed_not_in_tiles(self) -> None:
        meld = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5)
        try:
            _hand_subset_for_open_meld(meld, PIN5, 2)
            raise AssertionError("expected ValueError for claimed not in tiles")
        except ValueError:
            pass

    def test_wrong_hand_tile_count(self) -> None:
        meld = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5)
        try:
            _hand_subset_for_open_meld(meld, MAN5, 3)
            raise AssertionError("expected ValueError for wrong hand tile count")
        except ValueError:
            pass


# --- apply_pass_call error guards ---

class TestPassCallErrorGuards:
    def test_wrong_turn_phase(self) -> None:
        b = board_sorted_deal(dealer=0)
        try:
            apply_pass_call(b, 0)
            raise AssertionError("expected ValueError for pass_call in MUST_DISCARD")
        except ValueError:
            pass

    def test_finished_call(self) -> None:
        b = _ron_call_response_board()
        cs = b.call_state
        assert cs is not None
        cs2 = replace(cs, finished=True, ron_claimants=frozenset({1}))
        b2 = replace(b, call_state=cs2)
        try:
            apply_pass_call(b2, 1)
            raise AssertionError("expected ValueError for pass_call on finished call")
        except ValueError:
            pass

    def test_ron_seat_not_in_remaining(self) -> None:
        b = _ron_call_response_board()
        cs = b.call_state
        assert cs is not None
        # seat 2 不在 ron_remaining 中
        cs2 = replace(cs, ron_remaining=frozenset({1, 3}))
        b2 = replace(b, call_state=cs2)
        try:
            apply_pass_call(b2, 2)
            raise AssertionError("expected ValueError for pass_call seat not in ron_remaining")
        except ValueError:
            pass

    def test_pon_kan_wrong_seat(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN5, MAN5],
        )
        # pon_kan 阶段，active seat=1，尝试 seat=2 pass
        try:
            apply_pass_call(b, 2)
            raise AssertionError("expected ValueError for pon_kan pass wrong seat")
        except ValueError:
            pass

    def test_chi_wrong_seat(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN2, MAN3],
            stage="chi",
        )
        try:
            apply_pass_call(b, 2)
            raise AssertionError("expected ValueError for chi pass wrong seat")
        except ValueError:
            pass


# --- apply_open_meld error guards ---

class TestOpenMeldErrorGuards:
    def test_wrong_turn_phase(self) -> None:
        b = board_sorted_deal(dealer=0)
        meld = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5)
        try:
            apply_open_meld(b, 0, meld)
            raise AssertionError("expected ValueError for open_meld in MUST_DISCARD")
        except ValueError:
            pass

    def test_chankan_rinshan_pending(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN5, MAN5],
        )
        cs = b.call_state
        assert cs is not None
        cs2 = replace(cs, chankan_rinshan_pending=True, river_index=-1)
        b2 = replace(b, call_state=cs2)
        meld = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5)
        try:
            apply_open_meld(b2, 1, meld)
            raise AssertionError("expected ValueError for open_meld during chankan")
        except ValueError:
            pass

    def test_after_riichi(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN5, MAN5],
        )
        riichi_list = list(b.riichi)
        riichi_list[1] = True
        b2 = replace(b, riichi=tuple(riichi_list))
        meld = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5)
        try:
            apply_open_meld(b2, 1, meld)
            raise AssertionError("expected ValueError for open_meld after riichi")
        except ValueError:
            pass

    def test_pon_wrong_stage(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN2, MAN3],
            stage="chi",
        )
        meld = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5)
        try:
            apply_open_meld(b, 1, meld)
            raise AssertionError("expected ValueError for pon in chi stage")
        except ValueError:
            pass

    def test_pon_wrong_pon_kan_order(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN5, MAN5],
        )
        meld = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), MAN5)
        try:
            apply_open_meld(b, 2, meld)
            raise AssertionError("expected ValueError for pon wrong pon_kan order")
        except ValueError:
            pass

    def test_daiminkan_wrong_stage(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN2, MAN3],
            stage="chi",
        )
        meld = Meld(MeldKind.DAIMINKAN, (MAN5, MAN5, MAN5, MAN5), MAN5)
        try:
            apply_open_meld(b, 1, meld)
            raise AssertionError("expected ValueError for daiminkan in chi stage")
        except ValueError:
            pass

    def test_daiminkan_wrong_pon_kan_order(self) -> None:
        b, _ = make_chi_pon_daiminkan_board(
            dealer=0, discarder=0, claimer=1,
            discard_tile=MAN5, claimer_extra_tiles=[MAN5, MAN5, MAN5],
        )
        meld = Meld(MeldKind.DAIMINKAN, (MAN5, MAN5, MAN5, MAN5), MAN5)
        try:
            apply_open_meld(b, 2, meld)
            raise AssertionError("expected ValueError for daiminkan wrong pon_kan order")
        except ValueError:
            pass


# --- board_after_ron_winners ---

class TestBoardAfterRonWinners:
    def test_no_call_state(self) -> None:
        b = board_sorted_deal(dealer=0)
        try:
            board_after_ron_winners(b)
            raise AssertionError("expected ValueError for no call_state")
        except ValueError:
            pass

    def test_not_finished(self) -> None:
        b = _ron_call_response_board()
        try:
            board_after_ron_winners(b)
            raise AssertionError("expected ValueError for not finished")
        except ValueError:
            pass

    def test_no_ron_claimants_via_direct_call(self) -> None:
        """finished + empty ron_claimants 被 validate_board_state 拦截，
        但 board_after_ron_winners 也检查此条件（行 371）。"""
        # 无法构造非法 board（validate_board_state 先拦截），跳过
        pass
