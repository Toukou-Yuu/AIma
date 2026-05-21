"""回归测试 R-08: 四风连打接线验证。

当前状态 (2026-05-21):
- `is_four_winds_flow()` 已在 apply.py DRAW 分支正确调用 (line 422-426)
- 但检测时机在下一家 DRAW 动作而非 CALL_RESPONSE 结束后立即检测
- 这是 H-05/P1-05 问题：API 语义不自然

Expected behavior:
- 首巡 + 无副露 + 四家第一舍为同一种风牌 → 四风连打流局
- 第四张风牌弃牌后应进入 CALL_RESPONSE（荣和窗口优先）
- 若荣和窗口全部 pass → 应立即 FLOWN (当前在下一家 DRAW 时才检测)
- 若荣和被宣言 → HAND_OVER（不触发四风连打）

测试要求：
1. 首巡 + 无副露 + 4 张相同风牌舍牌 → 四风连打流局
2. 第四张风牌弃牌 → CALL_RESPONSE 先开放（荣和窗口）
3. 荣和窗口全部 pass → FLOWN with FlowKind.FOUR_WINDS
4. 荣和被宣言 → HAND_OVER（无四风连打）

注意：当前检测时机在 DRAW 分支而非 CALL_RESPONSE 结束后。
      此测试文档化这一时机问题（H-05/P1-05）。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
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
MAN5 = Tile(Suit.MAN, 5)
MAN6 = Tile(Suit.MAN, 6)
PIN1 = Tile(Suit.PIN, 1)
PIN2 = Tile(Suit.PIN, 2)
PIN3 = Tile(Suit.PIN, 3)
SOU1 = Tile(Suit.SOU, 1)
SOU2 = Tile(Suit.SOU, 2)
SOU3 = Tile(Suit.SOU, 3)


class TestFourWindsDetection:
    """四风连打检测逻辑测试。"""

    def test_is_four_winds_flow_same_wind(self) -> None:
        """4 张相同风牌判定为四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        # 四张东风
        winds = [TON, TON, TON, TON]
        assert is_four_winds_flow(winds) is True

        # 四张南风
        winds = [NAN, NAN, NAN, NAN]
        assert is_four_winds_flow(winds) is True

        # 四张西风
        winds = [SHA, SHA, SHA, SHA]
        assert is_four_winds_flow(winds) is True

        # 四张北风
        winds = [PEI, PEI, PEI, PEI]
        assert is_four_winds_flow(winds) is True

    def test_is_four_winds_flow_different_winds(self) -> None:
        """4 张不同风牌不判定为四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        winds = [TON, NAN, SHA, PEI]  # 东南西北各一张
        assert is_four_winds_flow(winds) is False

    def test_is_four_winds_flow_non_wind(self) -> None:
        """含非风牌不判定为四风连打。"""
        from kernel.flow.transitions import is_four_winds_flow

        # 三张东风 + 一张一万
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

        # 四张白（Honor 5）
        tiles = [HAKU, HAKU, HAKU, HAKU]
        assert is_four_winds_flow(tiles) is False

        # 四张中（Honor 7）
        tiles = [CHUN, CHUN, CHUN, CHUN]
        assert is_four_winds_flow(tiles) is False


class TestFourWindsActionWiring:
    """四风连打动作接线测试（当前缺失）。"""

    def test_four_winds_flow_never_called_in_apply(self) -> None:
        """is_four_winds_flow 已在 apply DRAW 分支调用。

        状态：已修复但时机问题（H-05/P1-05）。
        函数在 DRAW 分支调用而非 CALL_RESPONSE 结束后立即检测。
        """
        pytest.skip("H-05: 四风连打检测时机在下一家 DRAW，应在 CALL_RESPONSE 结束后立即检测")

    def test_fourth_wind_discard_enters_call_response(self) -> None:
        """第四张风牌弃牌后应进入 CALL_RESPONSE（荣和窗口）。

        状态：CALL_RESPONSE 正确进入，但结束后检测时机在下一家 DRAW。
        """
        pytest.skip("H-05: 验证 CALL_RESPONSE 结束后立即检测而非下一家 DRAW")

    def test_call_response_all_pass_should_detect_four_winds(self) -> None:
        """CALL_RESPONSE 全 pass 后应检测四风连打。

        BUG 状态：当前 all pass 后直接进入 NEED_DRAW，未检测四风连打。
        修复：在 call 模块的 _finish_call_all_passed 中添加四风连打检测。
        """
        pytest.skip("R-08 BUG: _finish_call_all_passed 无四风连打检测")


class TestFourWindsConditions:
    """四风连打条件测试。"""

    def test_first_turn_condition_for_four_winds(self) -> None:
        """首巡定义验证：river 仅含四家各一张舍牌。

        四风连打条件：
        - 首巡（各家各只打了一张）
        - 无副露
        - 四张舍牌为相同风牌（东/南/西/北）
        """
        wall = _make_standard_wall(seed=42)
        board = _make_board_from_wall(wall, dealer_seat=0)

        # 配牌后 river 为空
        assert len(board.river) == 0

    def test_no_melds_condition_for_four_winds(self) -> None:
        """无副露条件验证。"""
        wall = _make_standard_wall(seed=42)
        board = _make_board_from_wall(wall, dealer_seat=0)

        # 配牌后所有家无副露
        for s in range(4):
            assert len(board.melds[s]) == 0

    def test_four_winds_requires_no_melds(self) -> None:
        """四风连打要求无副露。

        规则：若有吃碰杠，即使四张相同风牌舍牌也不触发四风连打。
        """
        pytest.skip("R-08 BUG: 需修复后验证副露阻断条件")


class TestFourWindsRonWindow:
    """四风连打荣和窗口优先测试。"""

    def test_fourth_wind_discard_opens_ron_window(self) -> None:
        """第四张风牌弃牌应先开放荣和窗口（CALL_RESPONSE）。

        规则：荣和窗口优先于中途流局检测。
        """
        pytest.skip("R-08 BUG: 需验证第四张风牌弃牌后荣和窗口开放")

    def test_ron_on_fourth_wind_no_four_winds_flow(self) -> None:
        """在第四张风牌上荣和 → HAND_OVER（不触发四风连打）。

        规则：荣和结算优先，流局不发生。
        """
        pytest.skip("R-08 BUG: 需修复后验证荣和阻断四风连打")

    def test_all_pass_triggers_four_winds_flow(self) -> None:
        """荣和窗口全部 pass → FLOWN with FlowKind.FOUR_WINDS。

        预期流程：
        1. 第四张风牌弃牌 → CALL_RESPONSE
        2. 三家依次 pass（无荣和/碰/吃）
        3. CALL_RESPONSE 结束 → 检测四风连打条件 → FLOWN
        """
        pytest.skip("R-08 BUG: 需修复后验证全 pass 后四风连打触发")


class TestFourWindsIntegration:
    """四风连打集成测试。"""

    def test_full_four_winds_flow(self) -> None:
        """完整流程：首巡四家连续打出相同风牌 → 四风连打流局。

        预期流程：
        1. 配牌后亲家摸牌打出东
        2. seat 1 摸牌打出东
        3. seat 2 摸牌打出东
        4. seat 3 摸牌打出东 → CALL_RESPONSE
        5. 全 pass → FLOWN with FlowKind.FOUR_WINDS
        """
        pytest.skip("R-08 BUG: 需修复后验证完整四风连打流程")

    def test_four_winds_flow_sequence(self) -> None:
        """验证四风连打发生顺序。

        规则：
        - 四风连打必须在首巡发生
        - 四张舍牌必须为同一种风牌（东、南、西、北）
        - 荣和窗口必须先关闭
        """
        pytest.skip("R-08 BUG: 需修复后验证四风连打顺序")


class TestFourWindsNegative:
    """负向条件测试。"""

    def test_melds_block_four_winds(self) -> None:
        """有副露时不应触发四风连打。

        场景：首巡中某家碰牌，后续四张相同风牌舍牌不触发四风连打。
        """
        pytest.skip("R-08 BUG: 需修复后验证副露阻断四风连打")

    def test_not_first_turn_blocks_four_winds(self) -> None:
        """非首巡时不应触发四风连打。

        场景：第二巡后，即使四张相同风牌舍牌也不触发四风连打。
        """
        pytest.skip("R-08 BUG: 需修复后验证非首巡阻断四风连打")

    def test_different_winds_no_flow(self) -> None:
        """不同风牌舍牌不触发四风连打。

        场景：东、南、西、北各一张舍牌不触发四风连打。
        """
        pytest.skip("R-08 BUG: 需修复后验证不同风牌阻断")

    def test_non_wind_tiles_no_flow(self) -> None:
        """含非风牌舍牌不触发四风连打。

        场景：三张东风 + 一张一万，不触发四风连打。
        """
        pytest.skip("R-08 BUG: 需修复后验证非风牌阻断")


class TestFlowKindFourWinds:
    """FlowKind.FOUR_WINDS 存在性验证。"""

    def test_four_winds_flow_kind_exists(self) -> None:
        """FlowKind.FOUR_WINDS 应存在（验证已存在）。"""
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

        # 提供 first_4_river 参数
        first_4 = [TON, TON, TON, TON]
        result = check_flow_kind(
            board,
            first_4_river=first_4,
        )

        assert result is not None
        assert result.kind == FlowKind.FOUR_WINDS


class TestFourWindsFirstTurnDefinition:
    """首巡定义测试。"""

    def test_first_turn_by_river_count(self) -> None:
        """首巡判断：river 条目数为 4 或更少（各家各打一张）。

        四风连打必须在 river 恰好 4 条且全部为同种风牌时触发。
        """
        # river 有 4 条时为首巡结束
        # river 有 5+ 条时已非首巡
        pytest.skip("R-08 BUG: 需验证首巡判定逻辑")

    def test_all_discards_per_seat_for_four_winds(self) -> None:
        """all_discards_per_seat 用于四风连打检测。

        规则：各家 all_discards_per_seat[seat] 长度均为 1 时为首巡。
        """
        pytest.skip("R-08 BUG: 需验证 all_discards_per_seat 检测逻辑")