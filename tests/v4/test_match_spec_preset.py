"""P0-2 回归测试：MatchSpec.preset 应正确传递给 kernel。

Bug: GameEngine.new_match() 不传 match_preset 给 initial_table_snapshot()，
导致 TableSnapshot.match_preset 永远是 HANCHAN，should_match_end() 无法正确触发。

Root cause: src/arena/engine.py:60-64
"""

from __future__ import annotations

import pytest

from arena.engine import GameEngine
from experiments.schema import MatchSpec
from kernel.table.model import MatchPreset, PrevailingWind, RoundNumber, TableSnapshot
from kernel.table.transitions import should_match_end


class TestMatchSpecPresetPropagation:
    """验证 MatchSpec.preset 正确传递到 kernel state。"""

    def test_tonpuu_creates_tonpusen_kernel_state(self) -> None:
        """MatchSpec(preset="tonpuu") 应创建 match_preset == TONPUSEN 的 kernel state。"""
        engine = GameEngine()
        spec = MatchSpec(preset="tonpuu")
        state = engine.new_match(spec, seed=42)

        # 验证 match_preset 被正确设置
        assert state.table.match_preset == MatchPreset.TONPUSEN, (
            f"tonpuu preset 应创建 TONPUSEN kernel state，实际是 {state.table.match_preset}"
        )

    def test_hanchan_creates_hanchan_kernel_state(self) -> None:
        """MatchSpec(preset="hanchan") 应创建 match_preset == HANCHAN 的 kernel state。"""
        engine = GameEngine()
        spec = MatchSpec(preset="hanchan")
        state = engine.new_match(spec, seed=42)

        # 验证 match_preset 被正确设置
        assert state.table.match_preset == MatchPreset.HANCHAN, (
            f"hanchan preset 应创建 HANCHAN kernel state，实际是 {state.table.match_preset}"
        )

    def test_default_is_hanchan(self) -> None:
        """默认 preset 应为 hanchan。"""
        engine = GameEngine()
        spec = MatchSpec()  # 默认 preset
        state = engine.new_match(spec, seed=42)

        assert state.table.match_preset == MatchPreset.HANCHAN

    def test_none_spec_uses_hanchan_default(self) -> None:
        """spec=None 应使用默认 hanchan 配置。"""
        engine = GameEngine()
        state = engine.new_match(None, seed=42)

        assert state.table.match_preset == MatchPreset.HANCHAN


class TestShouldMatchEndForTonpuu:
    """验证 kernel 的 should_match_end() 对 tonpuu 正确工作。"""

    def test_tonpuu_ends_at_east_four(self) -> None:
        """东风战应在东四局亲流后终局。"""
        # 构造东四局的 TableSnapshot
        table = TableSnapshot(
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=0,
            kyoutaku=0,
            scores=(25000, 25000, 25000, 25000),
            match_preset=MatchPreset.TONPUSEN,
        )

        # 东风战：东四局应触发终局
        assert should_match_end(table), "东风战东四局应触发终局"

    def test_hanchan_not_ends_at_east_four(self) -> None:
        """半庄战在东四局不应终局。"""
        table = TableSnapshot(
            prevailing_wind=PrevailingWind.EAST,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=0,
            kyoutaku=0,
            scores=(25000, 25000, 25000, 25000),
            match_preset=MatchPreset.HANCHAN,
        )

        # 半庄：东四局不终局
        assert not should_match_end(table), "半庄东四局不应终局"

    def test_hanchan_ends_at_south_four(self) -> None:
        """半庄战应在南四局亲流后终局。"""
        table = TableSnapshot(
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=0,
            kyoutaku=0,
            scores=(25000, 25000, 25000, 25000),
            match_preset=MatchPreset.HANCHAN,
        )

        # 半庄：南四局应触发终局
        assert should_match_end(table), "半庄南四局应触发终局"

    def test_tonpuu_not_ends_at_south_four(self) -> None:
        """东风战不应到南四局（理论上不会发生，因为东四局已终局）。"""
        # 这是一个边界测试，验证逻辑一致性
        table = TableSnapshot(
            prevailing_wind=PrevailingWind.SOUTH,
            round_number=RoundNumber.FOUR,
            dealer_seat=0,
            honba=0,
            kyoutaku=0,
            scores=(25000, 25000, 25000, 25000),
            match_preset=MatchPreset.TONPUSEN,
        )

        # 东风战：南四局不应终局（按规则定义）
        # 注意：实际上东风战不应进入南场，这是逻辑一致性测试
        assert not should_match_end(table), "东风战南四局不应终局（按规则定义）"

    def test_tonpuu_not_ends_before_east_four(self) -> None:
        """东风战在东一至东三局不应终局。"""
        for round_num in [RoundNumber.ONE, RoundNumber.TWO, RoundNumber.THREE]:
            table = TableSnapshot(
                prevailing_wind=PrevailingWind.EAST,
                round_number=round_num,
                dealer_seat=0,
                honba=0,
                kyoutaku=0,
                scores=(25000, 25000, 25000, 25000),
                match_preset=MatchPreset.TONPUSEN,
            )
            assert not should_match_end(table), f"东风战东{round_num.value}局不应终局"


class TestIntegrationMatchPresetFlow:
    """集成测试：验证 preset 从 MatchSpec 流经 GameEngine 到 kernel。"""

    def test_full_flow_tonpuu(self) -> None:
        """完整流程：MatchSpec -> GameEngine -> kernel state -> should_match_end。"""
        engine = GameEngine()
        spec = MatchSpec(preset="tonpuu")
        state = engine.new_match(spec, seed=42)

        # 开局时不在终局状态
        initial_table = state.table
        assert initial_table.match_preset == MatchPreset.TONPUSEN
        assert initial_table.prevailing_wind == PrevailingWind.EAST
        assert initial_table.round_number == RoundNumber.ONE
        assert not should_match_end(initial_table), "开局不应终局"

    def test_full_flow_hanchan(self) -> None:
        """完整流程：hanchan preset。"""
        engine = GameEngine()
        spec = MatchSpec(preset="hanchan")
        state = engine.new_match(spec, seed=42)

        initial_table = state.table
        assert initial_table.match_preset == MatchPreset.HANCHAN
        assert initial_table.prevailing_wind == PrevailingWind.EAST
        assert initial_table.round_number == RoundNumber.ONE
        assert not should_match_end(initial_table), "开局不应终局"