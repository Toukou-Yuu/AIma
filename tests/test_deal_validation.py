"""deal.model validate_board_state 校验分支覆盖测试。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel.deal.model import BoardState, validate_board_state
from kernel.hand.melds import Meld, MeldKind
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from kernel.tiles.model import Suit, Tile
from kernel.wall.split import RINSHAN_COUNT, INDICATOR_COUNT, DeadWall, LIVE_WALL_SIZE
from tests.engine_helpers import board_sorted_deal, make_board_with_discard
from tests.call_helpers import clear_call_window

MAN1 = Tile(Suit.MAN, 1)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)


def _valid_board() -> BoardState:
    """返回一个合法的 MUST_DISCARD 状态。"""
    return board_sorted_deal(dealer=0)


def _need_draw_board() -> BoardState:
    """返回一个合法的 NEED_DRAW 状态。"""
    b = _valid_board()
    tile = next(iter(b.hands[0]))
    b2 = make_board_with_discard(dealer=0, discarder=0, discard_tile=tile, discarder_hand=b.hands[0])
    return clear_call_window(b2)


def _call_response_board() -> BoardState:
    """返回一个合法的 CALL_RESPONSE 状态。"""
    b = _valid_board()
    tile = next(iter(b.hands[0]))
    return make_board_with_discard(dealer=0, discarder=0, discard_tile=tile, discarder_hand=b.hands[0])


# --- 基础字段校验 ---

class TestBasicFieldValidation:
    def test_current_seat_out_of_range(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, current_seat=4))
            raise AssertionError("expected ValueError for current_seat=4")
        except ValueError:
            pass

    def test_live_wall_wrong_length(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, live_wall=b.live_wall[:10]))
            raise AssertionError("expected ValueError for wrong live_wall length")
        except ValueError:
            pass

    def test_live_draw_index_out_of_range(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, live_draw_index=999))
            raise AssertionError("expected ValueError for live_draw_index out of range")
        except ValueError:
            pass

    def test_revealed_indicators_empty(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, revealed_indicators=()))
            raise AssertionError("expected ValueError for empty revealed_indicators")
        except ValueError:
            pass

    def test_revealed_indicators_too_many(self) -> None:
        b = _valid_board()
        extra = b.revealed_indicators + (MAN1,) * (INDICATOR_COUNT + 1)
        try:
            validate_board_state(replace(b, revealed_indicators=extra))
            raise AssertionError("expected ValueError for too many revealed_indicators")
        except ValueError:
            pass

    def test_rinshan_draw_index_out_of_range(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, rinshan_draw_index=RINSHAN_COUNT + 1))
            raise AssertionError("expected ValueError for rinshan_draw_index out of range")
        except ValueError:
            pass

    def test_rinshan_without_tile(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, last_draw_was_rinshan=True, last_draw_tile=None))
            raise AssertionError("expected ValueError for rinshan without tile")
        except ValueError:
            pass


# --- 牌数守恒 ---

class TestTileConservation:
    def test_conservation_violated(self) -> None:
        b = _valid_board()
        # 从亲家手牌移除一张牌但不放回任何地方 → 总数 < 136
        h0 = b.hands[0].copy()
        tile = next(iter(h0))
        h0[tile] -= 1
        if h0[tile] == 0:
            del h0[tile]
        new_hands = (h0,) + b.hands[1:]
        try:
            validate_board_state(replace(b, hands=new_hands))
            raise AssertionError("expected ValueError for tile conservation violation")
        except ValueError:
            pass


# --- riichi / ippatsu / double_riichi ---

class TestRiichiValidation:
    def test_riichi_wrong_length(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, riichi=(True, True)))
            raise AssertionError("expected ValueError for riichi wrong length")
        except ValueError:
            pass

    def test_ippatsu_seat_out_of_range(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, ippatsu_eligible=frozenset({5})))
            raise AssertionError("expected ValueError for ippatsu seat out of range")
        except ValueError:
            pass

    def test_double_riichi_seat_out_of_range(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, double_riichi=frozenset({-1})))
            raise AssertionError("expected ValueError for double_riichi seat out of range")
        except ValueError:
            pass

    def test_double_riichi_not_in_riichi(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, riichi=(False, False, False, False), double_riichi=frozenset({1})))
            raise AssertionError("expected ValueError for double_riichi not in riichi")
        except ValueError:
            pass


# --- discards ---

class TestDiscardsValidation:
    def test_all_discards_wrong_length(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, all_discards_per_seat=((), (), ())))
            raise AssertionError("expected ValueError for all_discards wrong length")
        except ValueError:
            pass

    def test_called_discard_indices_wrong_length(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, called_discard_indices=(frozenset(), frozenset())))
            raise AssertionError("expected ValueError for called_discard_indices wrong length")
        except ValueError:
            pass

    def test_called_discard_index_out_of_range(self) -> None:
        b = _valid_board()
        new_called = (frozenset({5}), frozenset(), frozenset(), frozenset())
        try:
            validate_board_state(replace(b, called_discard_indices=new_called))
            raise AssertionError("expected ValueError for called_discard_index out of range")
        except ValueError:
            pass


# --- NEED_DRAW 阶段 ---

class TestNeedDrawValidation:
    def test_last_draw_tile_not_none(self) -> None:
        b = _need_draw_board()
        try:
            validate_board_state(replace(b, last_draw_tile=MAN1))
            raise AssertionError("expected ValueError for last_draw_tile in NEED_DRAW")
        except ValueError:
            pass

    def test_last_draw_was_rinshan(self) -> None:
        b = _need_draw_board()
        try:
            validate_board_state(replace(b, last_draw_was_rinshan=True, last_draw_tile=MAN1))
            raise AssertionError("expected ValueError for rinshan in NEED_DRAW")
        except ValueError:
            pass


# --- CALL_RESPONSE 阶段 ---

class TestCallResponseValidation:
    def test_no_call_state(self) -> None:
        b = _call_response_board()
        try:
            validate_board_state(replace(b, call_state=None))
            raise AssertionError("expected ValueError for CALL_RESPONSE without call_state")
        except ValueError:
            pass

    def test_last_draw_tile_not_none(self) -> None:
        b = _call_response_board()
        try:
            validate_board_state(replace(b, last_draw_tile=MAN1))
            raise AssertionError("expected ValueError for last_draw_tile in CALL_RESPONSE")
        except ValueError:
            pass

    def test_last_draw_was_rinshan(self) -> None:
        b = _call_response_board()
        try:
            validate_board_state(replace(b, last_draw_was_rinshan=True, last_draw_tile=MAN1))
            raise AssertionError("expected ValueError for rinshan in CALL_RESPONSE")
        except ValueError:
            pass

    def test_finished_without_ron_claimants(self) -> None:
        b = _call_response_board()
        cs = b.call_state
        assert cs is not None
        cs2 = replace(cs, finished=True, ron_claimants=frozenset())
        try:
            validate_board_state(replace(b, call_state=cs2))
            raise AssertionError("expected ValueError for finished without ron_claimants")
        except ValueError:
            pass

    def test_chankan_river_index_not_neg1(self) -> None:
        b = _call_response_board()
        cs = b.call_state
        assert cs is not None
        cs2 = replace(cs, chankan_rinshan_pending=True, river_index=0)
        try:
            validate_board_state(replace(b, call_state=cs2))
            raise AssertionError("expected ValueError for chankan with river_index != -1")
        except ValueError:
            pass


# --- unknown turn_phase ---

class TestUnknownTurnPhase:
    def test_unknown_phase(self) -> None:
        b = _valid_board()
        try:
            validate_board_state(replace(b, turn_phase="invalid_phase"))
            raise AssertionError("expected ValueError for unknown turn phase")
        except ValueError:
            pass


# --- wall/split DeadWall/WallSplit validation ---

class TestWallSplitValidation:
    def test_dead_wall_rinshan_wrong_length(self) -> None:
        try:
            DeadWall(rinshan=(MAN1,) * 3, ura_bases=(MAN1,) * INDICATOR_COUNT, indicators=(MAN1,) * INDICATOR_COUNT)
            raise AssertionError("expected ValueError for wrong rinshan length")
        except ValueError:
            pass

    def test_dead_wall_ura_bases_wrong_length(self) -> None:
        try:
            DeadWall(rinshan=(MAN1,) * RINSHAN_COUNT, ura_bases=(MAN1,) * 2, indicators=(MAN1,) * INDICATOR_COUNT)
            raise AssertionError("expected ValueError for wrong ura_bases length")
        except ValueError:
            pass

    def test_dead_wall_indicators_wrong_length(self) -> None:
        try:
            DeadWall(rinshan=(MAN1,) * RINSHAN_COUNT, ura_bases=(MAN1,) * INDICATOR_COUNT, indicators=(MAN1,) * 2)
            raise AssertionError("expected ValueError for wrong indicators length")
        except ValueError:
            pass

    def test_wall_split_live_wrong_length(self) -> None:
        from kernel.wall.split import WallSplit
        dw = DeadWall(rinshan=(MAN1,) * RINSHAN_COUNT, ura_bases=(MAN1,) * INDICATOR_COUNT, indicators=(MAN1,) * INDICATOR_COUNT)
        try:
            WallSplit(live=(MAN1,) * 10, dead=dw)
            raise AssertionError("expected ValueError for wrong live wall length")
        except ValueError:
            pass
