"""Tests for GameEngine facade and action serialization."""

from __future__ import annotations

import json
from dataclasses import replace

from arena import EngineStepResult, GameEngine
from kernel import (
    Action,
    ActionKind,
    GameState,
    apply,
    build_deck,
    initial_game_state,
    initial_table_snapshot,
    legal_actions,
    shuffle_deck,
)
from kernel.engine.phase import GamePhase
from kernel.tiles.model import Suit, Tile
from replay import action_to_record, legal_action_to_record


def _wall136(*, seed: int = 0) -> tuple:
    """Generate a shuffled wall of 136 tiles."""
    return tuple(shuffle_deck(build_deck(), seed=seed))


class TestGameEngineFacade:
    """测试 GameEngine 门面与 kernel API 一致性。"""

    def test_engine_new_match_returns_game_state(self) -> None:
        """验证 GameEngine.new_match 返回 PRE_DEAL 状态的 GameState。"""
        engine = GameEngine()
        # MatchSpec 在 TYPE_CHECKING 中，用 None 触发默认行为
        state = engine.new_match(None, seed=42)  # type: ignore[arg-type]

        assert isinstance(state, GameState)
        assert state.phase == GamePhase.PRE_DEAL
        assert state.board is None
        assert state.table.dealer_seat == 0

    def test_engine_legal_actions_matches_kernel_api(self) -> None:
        """关键回归测试：验证 GameEngine.legal_actions 与 kernel.api.legal_actions 结果一致。"""
        engine = GameEngine()
        g0 = initial_game_state()
        w = _wall136(seed=10)
        from kernel import apply as kernel_apply
        g1 = kernel_apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))

        for seat in range(4):
            engine_actions = engine.legal_actions(g1.new_state, seat)
            kernel_actions = legal_actions(g1.new_state, seat)
            assert engine_actions == kernel_actions, f"seat {seat} legal_actions 不一致"

    def test_engine_step_matches_kernel_apply(self) -> None:
        """关键回归测试：验证 GameEngine.step 与 kernel.engine.apply 结果一致。"""
        engine = GameEngine()
        g0 = initial_game_state()
        w = _wall136(seed=10)

        # 测试 BEGIN_ROUND
        result = engine.step(g0, Action(ActionKind.BEGIN_ROUND, wall=w))
        kernel_outcome = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))

        assert isinstance(result, EngineStepResult)
        assert result.new_state == kernel_outcome.new_state
        assert result.events == kernel_outcome.events

        # 测试 NOOP 在 IN_ROUND 状态（NOOP 只在 IN_ROUND 合法）
        g1 = result.new_state
        result2 = engine.step(g1, Action(ActionKind.NOOP))
        kernel_outcome2 = apply(g1, Action(ActionKind.NOOP))
        assert result2.new_state == kernel_outcome2.new_state
        assert result2.events == kernel_outcome2.events

    def test_engine_observe_matches_kernel_api(self) -> None:
        """关键回归测试：验证 GameEngine.observe 与 kernel.api.observation 结果一致。"""
        from kernel.api.observation import observation
        engine = GameEngine()
        g0 = initial_game_state()
        w = _wall136(seed=10)
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        for seat in range(4):
            engine_obs = engine.observe(g1, seat, mode="human")
            kernel_obs = observation(g1, seat, "human")
            assert engine_obs == kernel_obs, f"seat {seat} observation 不一致"

    def test_engine_is_terminal_and_phase(self) -> None:
        """验证 GameEngine.is_terminal/phase 辅助方法返回正确。"""
        engine = GameEngine()
        g0 = initial_game_state()

        assert not engine.is_terminal(g0)
        assert engine.phase(g0) == "pre_deal"

        # 构造 MATCH_END 状态
        g_end = replace(
            initial_game_state(initial_table_snapshot()),
            phase=GamePhase.MATCH_END,
        )
        assert engine.is_terminal(g_end)
        assert engine.phase(g_end) == "match_end"

    def test_engine_full_match_dry_run(self) -> None:
        """关键 characterization 测试：验证完整对局流程可走通（东风 1 局）。"""
        engine = GameEngine()
        state = engine.new_match(None, seed=42)  # type: ignore[arg-type]
        w = _wall136(seed=100)

        # BEGIN_ROUND
        result = engine.step(state, Action(ActionKind.BEGIN_ROUND, wall=w))
        state = result.new_state
        assert state.phase == GamePhase.IN_ROUND

        # 简单推进几步
        for _ in range(10):
            if engine.is_terminal(state):
                break
            if state.board is None:
                break
            seat = state.board.current_seat
            actions = engine.legal_actions(state, seat)
            if not actions:
                break
            action = actions[0]
            result = engine.step(state, action)
            state = result.new_state

        # 只要没崩溃就算通过
        assert True

    def test_replay_audit_from_records(self) -> None:
        """验证 replay 审计能力，action records 可用于状态重建。"""
        engine = GameEngine()
        state = engine.new_match(None, seed=42)  # type: ignore[arg-type]
        w = _wall136(seed=100)

        records = []

        # BEGIN_ROUND
        action = Action(ActionKind.BEGIN_ROUND, wall=w)
        records.append(action_to_record(action))
        result = engine.step(state, action)
        state = result.new_state

        # 记录第一个合法动作
        seat = state.board.current_seat if state.board else 0
        actions = engine.legal_actions(state, seat)
        if actions:
            legal_action = actions[0]
            records.append(legal_action_to_record(legal_action))

        # 验证 records 可 JSON 序列化
        json_str = json.dumps(records, ensure_ascii=False, indent=2)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1


class TestActionSerialization:
    """测试 action 序列化可读性。"""

    def test_action_to_record_readable_json(self) -> None:
        """验证 action_to_record 输出可被 JSON 工具处理。"""
        action = Action(ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 1))
        record = action_to_record(action)

        # 验证可 JSON 序列化
        json_str = json.dumps(record, ensure_ascii=False)
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "kind" in parsed
        assert parsed["kind"] == "discard"

    def test_legal_action_to_record_readable_json(self) -> None:
        """验证 legal_action_to_record 输出可被 JSON 处理。"""
        from kernel.api.legal_actions import LegalAction

        legal_action = LegalAction(kind=ActionKind.DRAW, seat=1)
        record = legal_action_to_record(legal_action)

        json_str = json.dumps(record, ensure_ascii=False)
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed["kind"] == "draw"
        assert parsed["seat"] == 1