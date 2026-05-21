"""K12 局推进与终局测试。"""

from __future__ import annotations

from dataclasses import replace

from kernel.deal import build_board_after_split
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.flow.model import TenpaiResult
from kernel.table.model import MatchPreset, PrevailingWind, RoundNumber, initial_table_snapshot
from kernel.table.transitions import (
    advance_round,
    compute_match_ranking,
    final_settlement,
    should_match_end,
)
from kernel.tiles.deck import build_deck
from kernel.wall.split import split_wall


class TestAdvanceRound:
    """局推进逻辑测试。"""

    def test_continue_dealer_no_change(self) -> None:
        """连庄：局序、亲席、场风不变，本场由调用方处理。"""
        table = initial_table_snapshot(
            dealer_seat=0,
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.ONE,
            honba=1,
        )
        new_table = advance_round(table, continue_dealer=True)

        assert new_table.dealer_seat == 0
        assert new_table.prevailing_wind == PrevailingWind.EAST
        assert new_table.round_number == RoundNumber.ONE
        # honba 应由调用方（settle_*_table 或 settle_flow）处理

    def test_noten_dealer_east1(self) -> None:
        """亲流：东一局→东二局，亲席轮转。"""
        table = initial_table_snapshot(
            dealer_seat=0,
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.ONE,
            honba=0,
        )
        # 假设 honba 已被 settle_flow 重置
        new_table = advance_round(table, continue_dealer=False)

        assert new_table.dealer_seat == 1
        assert new_table.prevailing_wind == PrevailingWind.EAST
        assert new_table.round_number == RoundNumber.TWO

    def test_noten_dealer_east4(self) -> None:
        """亲流：东四局→南一局。"""
        table = initial_table_snapshot(
            dealer_seat=0,
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.FOUR,
            honba=0,
        )
        new_table = advance_round(table, continue_dealer=False)

        assert new_table.dealer_seat == 1
        assert new_table.prevailing_wind == PrevailingWind.SOUTH
        assert new_table.round_number == RoundNumber.ONE

    def test_noten_dealer_south4(self) -> None:
        """亲流：南四局→终局（调用方应检查 should_match_end）。"""
        table = initial_table_snapshot(
            dealer_seat=0,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            honba=0,
        )
        new_table = advance_round(table, continue_dealer=False)

        assert new_table.dealer_seat == 1
        assert new_table.prevailing_wind == PrevailingWind.SOUTH
        assert new_table.round_number == RoundNumber.FOUR


class TestShouldMatchEnd:
    """终局判定测试。"""

    def test_east4_noten_should_end(self) -> None:
        """东风战：东四局亲流后终局。"""
        table = initial_table_snapshot(
            match_preset=MatchPreset.TONPUSEN,
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.FOUR,
            honba=0,
        )
        assert should_match_end(table) is True

    def test_east3_noten_should_not_end(self) -> None:
        """东风战：东三局亲流后不终局。"""
        table = initial_table_snapshot(
            match_preset=MatchPreset.TONPUSEN,
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.THREE,
            honba=0,
        )
        assert should_match_end(table) is False

    def test_hanchan_south4_noten_should_end(self) -> None:
        """半庄战：南四局亲流后终局。"""
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            honba=0,
        )
        assert should_match_end(table) is True

    def test_hanchan_east4_noten_should_not_end(self) -> None:
        """半庄战：东四局亲流后不终局（应进入南场）。"""
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.FOUR,
            honba=0,
        )
        assert should_match_end(table) is False

    def test_hanchan_south3_noten_should_not_end(self) -> None:
        """半庄战：南三局亲流后不终局。"""
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.THREE,
            honba=0,
        )
        assert should_match_end(table) is False


class TestComputeMatchRanking:
    """名次计算测试。"""

    def test_no_tie(self) -> None:
        """无同分：正常排序。"""
        table = initial_table_snapshot(
            starting_points=25000,
            dealer_seat=0,
        )
        # 手动设置分数：席次 0=30000, 1=20000, 2=40000, 3=10000
        table = replace(table, scores=(30000, 20000, 40000, 10000))

        ranking = compute_match_ranking(table)

        # 期望：席次 2 是 1 位 (40000), 席次 0 是 2 位 (30000)
        #       席次 1 是 3 位 (20000), 席次 3 是 4 位 (10000)
        assert ranking == (2, 3, 1, 4)

    def test_two_way_tie_first(self) -> None:
        """两家同分 1 位：并列 1 位。"""
        table = initial_table_snapshot(starting_points=25000)
        # 席次 0=35000, 1=35000, 2=20000, 3=10000
        table = replace(table, scores=(35000, 35000, 20000, 10000))

        ranking = compute_match_ranking(table)

        # 期望：席次 0 和 1 并列 1 位，席次 2 是 3 位，席次 3 是 4 位
        assert ranking == (1, 1, 3, 4)

    def test_three_way_tie(self) -> None:
        """三家同分。"""
        table = initial_table_snapshot(starting_points=25000)
        # 席次 0=25000, 1=25000, 2=25000, 3=25000
        table = replace(table, scores=(25000, 25000, 25000, 25000))

        ranking = compute_match_ranking(table)

        # 期望：四家并列 1 位
        assert ranking == (1, 1, 1, 1)


class TestFinalSettlement:
    """终局最终结算测试。"""

    def test_supply_to_first_place(self) -> None:
        """终局供托归 1 位。"""
        table = initial_table_snapshot(
            starting_points=25000,
            kyoutaku=3000,  # 3 根供托
        )
        # 席次 0=30000, 1=20000, 2=40000, 3=10000
        table = replace(table, scores=(30000, 20000, 40000, 10000))

        ranking, new_table = final_settlement(table)

        # 期望：席次 2 是 1 位，获得 3000 供托
        assert ranking == (2, 3, 1, 4)
        assert new_table.scores == (30000, 20000, 43000, 10000)
        assert new_table.kyoutaku == 0

    def test_supply_split_on_tie(self) -> None:
        """供托均分给并列 1 位。"""
        table = initial_table_snapshot(
            starting_points=25000,
            kyoutaku=3000,  # 3 根供托
        )
        # 席次 0=35000, 1=35000, 2=20000, 3=10000
        table = replace(table, scores=(35000, 35000, 20000, 10000))

        ranking, new_table = final_settlement(table)

        # 期望：席次 0 和 1 并列 1 位，各得 1500（3000//2）
        assert ranking == (1, 1, 3, 4)
        assert new_table.scores == (36500, 36500, 20000, 10000)
        assert new_table.kyoutaku == 0

    def test_supply_remainder_distributed(self) -> None:
        """供托均分余数按排序顺序依次分配（点棒守恒）。"""
        table = initial_table_snapshot(
            starting_points=25000,
            kyoutaku=1000,  # 1 根供托
        )
        # 三家并列 1 位
        table = replace(table, scores=(30000, 30000, 30000, 10000))

        ranking, new_table = final_settlement(table)

        # 期望：三家各得 333（1000//3），余数 1 分给第一个（seat 0）
        assert ranking == (1, 1, 1, 4)
        # 修复后：seat 0 = 30000 + 333 + 1 = 30334，其余 = 30000 + 333 = 30333
        assert new_table.scores == (30334, 30333, 30333, 10000)
        assert new_table.kyoutaku == 0
        # 验证点棒守恒
        total_before = 30000 + 30000 + 30000 + 10000 + 1000
        total_after = 30334 + 30333 + 30333 + 10000
        assert total_before == total_after


class TestR09DealerWinAtSouth4ShouldContinue:
    """R-09 回归测试：南四局亲家和了应连庄而非终局。

    Root cause: should_match_end() 在检查 continue_dealer 之前被调用。
    Expected: 亲家和了 → 连庄（dealer_seat 不变）→ 下一局 IN_ROUND。
    """

    def test_dealer_win_at_south4_hand_over_should_continue(self) -> None:
        """南四局亲家和了后 HAND_OVER → NOOP → IN_ROUND（连庄）。"""
        # 构造南四局场况
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=2,
        )

        # 构造 HAND_OVER 状态：亲家（seat 0）荣和
        state = GameState(
            phase=GamePhase.HAND_OVER,
            table=table,
            board=None,  # HAND_OVER 不需要 board
            ron_winners=frozenset({0}),  # 亲家和了
        )

        # 准备牌山用于下一局
        wall = tuple(build_deck())

        # 执行 NOOP 推进
        outcome = apply(state, Action(kind=ActionKind.NOOP, wall=wall))

        # 验证：应连庄（IN_ROUND），而非终局（MATCH_END）
        assert outcome.new_state.phase == GamePhase.IN_ROUND
        assert outcome.new_state.table.dealer_seat == 0  # 亲席不变
        assert outcome.new_state.table.prevailing_wind == PrevailingWind.SOUTH  # 场风不变
        assert outcome.new_state.table.round_number == RoundNumber.FOUR  # 局序不变
        # honba 由 settlement 计算，此处不验证

    def test_dealer_win_at_south4_not_match_end(self) -> None:
        """验证：南四局亲家和了后，advance_round(continue_dealer=True) 正确。"""
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=0,
        )

        # 直接验证 advance_round 连庄行为
        new_table = advance_round(table, continue_dealer=True)

        # 连庄：亲席、场风、局序不变
        assert new_table.dealer_seat == 0
        assert new_table.prevailing_wind == PrevailingWind.SOUTH
        assert new_table.round_number == RoundNumber.FOUR


class TestR09DealerTenpaiAtSouth4FlowShouldContinue:
    """R-09 回归测试：南四局亲家听牌流局应连庄而非终局。

    Root cause: advance_after_flow() 中 should_match_end() 在检查 continue_dealer 之前被调用。
    Expected: 亲家听牌 → 连庄（dealer_seat 不变）→ 下一局 IN_ROUND。
    """

    def test_dealer_tenpai_at_south4_flow_should_continue(self) -> None:
        """南四局亲家听牌流局后 FLOWN → NOOP → IN_ROUND（连庄）。"""
        # 构造南四局场况
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=1,
        )

        # 构造 FLOWN 状态：亲家（seat 0）听牌
        state = GameState(
            phase=GamePhase.FLOWN,
            table=table,
            board=None,  # FLOWN 不需要 board
            tenpai_result=TenpaiResult(tenpai_seats=frozenset({0})),  # 亲家听牌
        )

        # 准备牌山用于下一局
        wall = tuple(build_deck())

        # 执行 NOOP 推进
        outcome = apply(state, Action(kind=ActionKind.NOOP, wall=wall))

        # 验证：应连庄（IN_ROUND），而非终局（MATCH_END）
        assert outcome.new_state.phase == GamePhase.IN_ROUND
        assert outcome.new_state.table.dealer_seat == 0  # 亲席不变
        assert outcome.new_state.table.prevailing_wind == PrevailingWind.SOUTH  # 场风不变
        assert outcome.new_state.table.round_number == RoundNumber.FOUR  # 局序不变

    def test_dealer_noten_at_south4_flow_should_end(self) -> None:
        """南四局亲家不听牌流局应终局（对照组）。"""
        # 构造南四局场况
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=0,
        )

        # 构造 FLOWN 状态：亲家（seat 0）不听牌（其他家听牌）
        state = GameState(
            phase=GamePhase.FLOWN,
            table=table,
            board=None,
            tenpai_result=TenpaiResult(tenpai_seats=frozenset({1, 2})),  # 非亲家听牌
        )

        # 准备牌山
        wall = tuple(build_deck())

        # 执行 NOOP 推进
        outcome = apply(state, Action(kind=ActionKind.NOOP, wall=wall))

        # 验证：应终局（MATCH_END），而非连庄
        assert outcome.new_state.phase == GamePhase.MATCH_END

    def test_child_win_at_south4_hand_over_should_change_dealer(self) -> None:
        """南四局子家和了后应亲流（对照组，验证 continue_dealer=False 路径）。"""
        # 构造南四局场况
        table = initial_table_snapshot(
            match_preset=MatchPreset.HANCHAN,
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=0,
        )

        # 构造 HAND_OVER 状态：子家（seat 1）荣和
        state = GameState(
            phase=GamePhase.HAND_OVER,
            table=table,
            board=None,
            ron_winners=frozenset({1}),  # 子家和了
        )

        # 准备牌山
        wall = tuple(build_deck())

        # 执行 NOOP 推进
        outcome = apply(state, Action(kind=ActionKind.NOOP, wall=wall))

        # 验证：应终局（MATCH_END），因为南四局亲流后终局
        assert outcome.new_state.phase == GamePhase.MATCH_END
