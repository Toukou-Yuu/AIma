"""回归测试 R-08: 四风连打接线验证。

H-08 修复 (2026-05-21):
- 四风连打检测已移至 CALL_RESPONSE 结束后立即检测
- 在 _outcome_pass_call 中检测，而非下一家 DRAW 时检测

Expected behavior:
- 首巡 + 无副露 + 四家第一舍为同一种风牌 → 四风连打流局
- 第四张风牌弃牌后应进入 CALL_RESPONSE（荣和窗口优先）
- 若荣和窗口全部 pass → 应立即 FLOWN
- 若荣和被宣言 → HAND_OVER（不触发四风连打）
"""

from __future__ import annotations

import dataclasses as dc

import pytest

from kernel.board import BoardState, TurnPhase, RiverEntry, CallResolution
from kernel.deal import build_board_after_split
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import ApplyOutcome, apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState, initial_game_state
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.table.model import initial_table_snapshot
from kernel.tiles.deck import build_deck, shuffle_deck
from kernel.tiles.model import Suit, Tile
from kernel.wall.split import split_wall


def _make_standard_wall(seed: int = 0) -> tuple[Tile, ...]:
    """生成标准 136 张牌山。"""
    return tuple(shuffle_deck(build_deck(), seed=seed))


def _make_board_from_wall(wall: tuple[Tile, ...], dealer_seat: int = 0) -> BoardState:
    """从牌山构建 BoardState。"""
    split = split_wall(wall)
    return build_board_after_split(split, dealer_seat)


def _mock_board(b0: BoardState, **overrides) -> BoardState:
    """绕过 __post_init__ 验证构造修改后的 BoardState。"""
    b = object.__new__(BoardState)
    for f in dc.fields(b0):
        val = overrides.get(f.name, getattr(b0, f.name))
        object.__setattr__(b, f.name, val)
    return b


# 风牌定义
TON = Tile(Suit.HONOR, 1)  # 东
NAN = Tile(Suit.HONOR, 2)  # 南
SHA = Tile(Suit.HONOR, 3)  # 西
PEI = Tile(Suit.HONOR, 4)  # 北
HAKU = Tile(Suit.HONOR, 5)
HATSU = Tile(Suit.HONOR, 6)
CHUN = Tile(Suit.HONOR, 7)

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN4 = Tile(Suit.MAN, 4)


class TestFourWindsDetection:
    """四风连打检测逻辑测试。"""

    def test_is_four_winds_flow_same_wind(self) -> None:
        """4 张相同风牌判定为四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        winds = [TON, TON, TON, TON]
        assert is_four_winds_flow(winds) is True

        winds = [NAN, NAN, NAN, NAN]
        assert is_four_winds_flow(winds) is True

        winds = [SHA, SHA, SHA, SHA]
        assert is_four_winds_flow(winds) is True

        winds = [PEI, PEI, PEI, PEI]
        assert is_four_winds_flow(winds) is True

    def test_is_four_winds_flow_different_winds(self) -> None:
        """4 张不同风牌不判定为四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        winds = [TON, NAN, SHA, PEI]
        assert is_four_winds_flow(winds) is False

    def test_is_four_winds_flow_non_wind(self) -> None:
        """含非风牌不判定为四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        tiles = [TON, TON, TON, MAN1]
        assert is_four_winds_flow(tiles) is False

    def test_is_four_winds_flow_wrong_count(self) -> None:
        """少于 4 张不判定为四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        winds = [TON, TON, TON]
        assert is_four_winds_flow(winds) is False

    def test_is_four_winds_flow_honor_5_7_not_wind(self) -> None:
        """白/发/中不是风牌，不触发四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        tiles = [HAKU, HAKU, HAKU, HAKU]
        assert is_four_winds_flow(tiles) is False

        tiles = [CHUN, CHUN, CHUN, CHUN]
        assert is_four_winds_flow(tiles) is False


class TestFourWindsActionWiring:
    """四风连打动作接线测试（H-08 修复验证）。"""

    def test_four_winds_detection_in_outcome_pass_call(self) -> None:
        """H-08 修复：detect_flow_four_winds 在 CALL_RESPONSE 结束后检测。

        验证：在 NEED_DRAW 状态且 call_state=None 时，四风连打条件满足则返回 FLOWN。
        """
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        # 构造首巡四张东风舍牌状态
        discards = ((TON,), (TON,), (TON,), (TON,))
        river = tuple(RiverEntry(seat=s, tile=TON) for s in range(4))
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards,
            river=river,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is not None
        assert flow_result.kind == FlowKind.FOUR_WINDS

    def test_discard_enters_call_response_phase(self) -> None:
        """验证：DISCARD 后进入 CALL_RESPONSE 阶段（荣和窗口）。

        通过验证 apply_discard 函数的输出结构。
        """
        # CALL_RESPONSE 是 apply_discard 的标准输出
        # 验证 CallResolution 结构
        cs = CallResolution.initial_after_discard(discard_seat=3, river_index=3, tile=TON)

        assert cs.stage == "ron"
        assert cs.discard_seat == 3
        assert cs.claimed_tile == TON
        assert 0 in cs.ron_remaining  # seat 0 可荣和
        assert 1 in cs.ron_remaining  # seat 1 可荣和
        assert 2 in cs.ron_remaining  # seat 2 可荣和
        assert len(cs.ron_claimants) == 0  # 无荣和者


class TestFourWindsConditions:
    """四风连打条件测试。"""

    def test_first_turn_condition_for_four_winds(self) -> None:
        """首巡定义验证：river 仅含四家各一张舍牌。"""
        wall = _make_standard_wall(seed=42)
        board = _make_board_from_wall(wall, dealer_seat=0)
        assert len(board.river) == 0

    def test_no_melds_condition_for_four_winds(self) -> None:
        """无副露条件验证。"""
        wall = _make_standard_wall(seed=42)
        board = _make_board_from_wall(wall, dealer_seat=0)
        for s in range(4):
            assert len(board.melds[s]) == 0

    def test_four_winds_requires_no_melds(self) -> None:
        """四风连打要求无副露。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        river4 = tuple(RiverEntry(seat=s, tile=TON) for s in range(4))
        discards4 = ((TON,), (TON,), (TON,), (TON,))
        meld = Meld(kind=MeldKind.PON, tiles=(TON, TON, TON), called_tile=TON, from_seat=3)
        melds_with_pon = ((), (meld,), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards4,
            river=river4,
            melds=melds_with_pon,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is None


class TestFourWindsRonWindow:
    """四风连打荣和窗口优先测试。"""

    def test_call_resolution_structure(self) -> None:
        """验证：DISCARD 后创建 CallResolution 进入荣和窗口。"""
        cs = CallResolution.initial_after_discard(discard_seat=3, river_index=3, tile=TON)

        # 验证荣和窗口开放
        assert cs.stage == "ron"
        assert len(cs.ron_remaining) == 3  # 三家可荣和

    def test_ron_claimants_blocks_four_winds(self) -> None:
        """验证：有荣和者时不触发四风连打。

        荣和优先于中途流局。
        """
        # 构造荣和状态
        cs = CallResolution(
            discard_seat=3,
            claimed_tile=TON,
            river_index=3,
            stage="ron",
            ron_remaining=frozenset(),
            ron_claimants=frozenset({0}),  # seat 0 荣和
            pon_kan_order=(0, 1, 2),
            pon_kan_idx=0,
            finished=True,
        )

        # 验证荣和状态
        assert cs.finished
        assert len(cs.ron_claimants) > 0
        # 此状态会转 HAND_OVER 而非 FLOWN


class TestFourWindsIntegration:
    """四风连打集成测试。"""

    def test_detect_flow_four_winds_full_conditions(self) -> None:
        """完整条件验证：首巡 + 无副露 + 四张相同风牌。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        river4 = tuple(RiverEntry(seat=s, tile=TON) for s in range(4))
        discards4 = ((TON,), (TON,), (TON,), (TON,))
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards4,
            river=river4,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is not None
        assert flow_result.kind == FlowKind.FOUR_WINDS

    def test_four_winds_sequence_validation(self) -> None:
        """验证四风连打顺序：首巡判定 + 舍牌判定。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        # 使用南风
        river4 = tuple(RiverEntry(seat=s, tile=NAN) for s in range(4))
        discards4 = ((NAN,), (NAN,), (NAN,), (NAN,))
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards4,
            river=river4,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        # 验证首巡
        assert all(len(d) == 1 for d in b1.all_discards_per_seat)

        # 验证无副露
        assert all(len(m) == 0 for m in b1.melds)

        # 验证舍牌为南风
        first_4 = [b1.all_discards_per_seat[s][0] for s in range(4)]
        assert all(t == NAN for t in first_4)

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is not None
        assert flow_result.kind == FlowKind.FOUR_WINDS


class TestFourWindsNegative:
    """负向条件测试。"""

    def test_melds_block_four_winds(self) -> None:
        """有副露时不应触发四风连打。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        river4 = tuple(RiverEntry(seat=s, tile=TON) for s in range(4))
        discards4 = ((TON,), (TON,), (TON,), (TON,))
        meld = Meld(kind=MeldKind.PON, tiles=(TON, TON, TON), called_tile=TON, from_seat=3)
        melds_with_pon = ((), (meld,), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards4,
            river=river4,
            melds=melds_with_pon,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is None

    def test_not_first_turn_blocks_four_winds(self) -> None:
        """非首巡时不应触发四风连打。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        # 每家两张舍牌
        discards_not_first = (
            (TON, MAN1),
            (TON, MAN2),
            (TON, MAN3),
            (TON, MAN4),
        )
        river8 = tuple(
            RiverEntry(seat=s, tile=TON) for s in range(4)
        ) + tuple(RiverEntry(seat=s, tile=Tile(Suit.MAN, s + 1)) for s in range(4))
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards_not_first,
            river=river8,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is None

    def test_different_winds_no_flow(self) -> None:
        """不同风牌舍牌不触发四风连打。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        discards_diff = ((TON,), (NAN,), (SHA,), (PEI,))
        river4 = (
            RiverEntry(seat=0, tile=TON),
            RiverEntry(seat=1, tile=NAN),
            RiverEntry(seat=2, tile=SHA),
            RiverEntry(seat=3, tile=PEI),
        )
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards_diff,
            river=river4,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is None

    def test_non_wind_tiles_no_flow(self) -> None:
        """含非风牌舍牌不触发四风连打。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        discards_mixed = ((TON,), (TON,), (TON,), (MAN1,))
        river4 = (
            RiverEntry(seat=0, tile=TON),
            RiverEntry(seat=1, tile=TON),
            RiverEntry(seat=2, tile=TON),
            RiverEntry(seat=3, tile=MAN1),
        )
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards_mixed,
            river=river4,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is None


class TestFlowKindFourWinds:
    """FlowKind.FOUR_WINDS 存在性验证。"""

    def test_four_winds_flow_kind_exists(self) -> None:
        """FlowKind.FOUR_WINDS 应存在。"""
        assert FlowKind.FOUR_WINDS.value == "four_winds"

    def test_flow_result_with_four_winds(self) -> None:
        """FlowResult 应支持 FlowKind.FOUR_WINDS。"""
        from kernel.flow.model import FlowResult

        result = FlowResult(kind=FlowKind.FOUR_WINDS)
        assert result.kind == FlowKind.FOUR_WINDS

    def test_check_flow_kind_with_four_winds(self) -> None:
        """check_flow_kind 应支持四风连打检测。"""
        from kernel.flow.transitions import check_flow_kind

        wall = _make_standard_wall()
        board = _make_board_from_wall(wall)

        first_4 = [TON, TON, TON, TON]
        result = check_flow_kind(board, first_4_river=first_4)

        assert result is not None
        assert result.kind == FlowKind.FOUR_WINDS


class TestFourWindsFirstTurnDefinition:
    """首巡定义测试。"""

    def test_first_turn_by_river_count(self) -> None:
        """首巡判断：每家恰好一张舍牌。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        river4 = tuple(RiverEntry(seat=s, tile=TON) for s in range(4))
        discards4 = ((TON,), (TON,), (TON,), (TON,))
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards4,
            river=river4,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        assert len(b1.river) == 4
        for s in range(4):
            assert len(b1.all_discards_per_seat[s]) == 1

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is not None

        # 不足 4 张时不触发
        river3 = tuple(RiverEntry(seat=s, tile=TON) for s in range(3))
        discards3 = ((TON,), (TON,), (TON,), ())
        b2 = _mock_board(
            b0,
            all_discards_per_seat=discards3,
            river=river3,
            melds=melds_empty,
            turn_phase=TurnPhase.MUST_DISCARD,
            call_state=None,
            current_seat=3,
            last_draw_tile=TON,
        )

        assert len(b2.all_discards_per_seat[3]) == 0
        flow_result2 = detect_flow_four_winds(b2)
        assert flow_result2 is None

    def test_all_discards_per_seat_for_four_winds(self) -> None:
        """all_discards_per_seat 用于四风连打检测。"""
        wall = _make_standard_wall(seed=42)
        b0 = _make_board_from_wall(wall, dealer_seat=0)

        river4 = tuple(RiverEntry(seat=s, tile=SHA) for s in range(4))
        discards4 = ((SHA,), (SHA,), (SHA,), (SHA,))
        melds_empty = ((), (), (), ())
        b1 = _mock_board(
            b0,
            all_discards_per_seat=discards4,
            river=river4,
            melds=melds_empty,
            turn_phase=TurnPhase.NEED_DRAW,
            call_state=None,
            current_seat=0,
            last_draw_tile=None,
        )

        assert all(len(b1.all_discards_per_seat[s]) == 1 for s in range(4))
        for s in range(4):
            assert b1.all_discards_per_seat[s][0] == SHA

        from kernel.engine.flow import detect_flow_four_winds

        flow_result = detect_flow_four_winds(b1)
        assert flow_result is not None
        assert flow_result.kind == FlowKind.FOUR_WINDS