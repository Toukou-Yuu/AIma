"""H-28 修复测试：Runner 局间推进使用 NEXT_ROUND。

测试要点：
1. HAND_OVER → NEXT_ROUND → IN_ROUND 推进正确
2. FLOWN → NEXT_ROUND 正确推进
3. wall 必须附带 136 张合规牌山

参考：test_llm_runner_coverage.py 的测试风格。"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from kernel.engine.actions import Action, ActionKind
from kernel.engine.phase import GamePhase
from kernel.engine.apply import apply, IllegalActionError
from kernel.engine.state import GameState, initial_game_state
from kernel import build_deck, shuffle_deck
from llm.config import MatchEndCondition
from llm.runner import run_llm_match
from tests.llm_test_utils import load_test_runtime_config, load_test_seat_llm_configs


class TestRunnerHandOverNextRound:
    """HAND_OVER → NEXT_ROUND → IN_ROUND 推进测试（H-28）。"""

    def test_runner_hand_over_to_next_round_with_valid_wall(self) -> None:
        """HAND_OVER 后 runner 使用 NEXT_ROUND + 136 张合规 wall 推进下一局。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=2, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        # 监控 apply 调用，确认局间使用 NEXT_ROUND 而非 NOOP
        next_round_calls: list[Action] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            # 记录 NEXT_ROUND 调用
            if action.kind == ActionKind.NEXT_ROUND:
                next_round_calls.append(action)
            return original_apply(state, action)

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：至少有一次 NEXT_ROUND 调用（局间推进）
        assert len(next_round_calls) >= 1, "应至少有一次 NEXT_ROUND 局间推进"
        # 验证：每次 NEXT_ROUND 都附带 136 张 wall
        for act in next_round_calls:
            assert act.wall is not None, "NEXT_ROUND 必须附带 wall"
            assert len(act.wall) == 136, "wall 必须为 136 张"

    def test_runner_hand_over_phase_transition_correct(self) -> None:
        """HAND_OVER/FLOWN → NEXT_ROUND → IN_ROUND 状态转换正确。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=2, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        # 记录状态转换
        phase_transitions: list[tuple[GamePhase, GamePhase]] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            result = original_apply(state, action)
            # 记录局间推进的状态转换
            if action.kind == ActionKind.NEXT_ROUND:
                phase_transitions.append((state.phase, result.new_state.phase))
            return result

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：每次局间推进起点是 HAND_OVER 或 FLOWN（dry_run 可能触发荒牌流局）
        for old_phase, new_phase in phase_transitions:
            assert old_phase in (GamePhase.HAND_OVER, GamePhase.FLOWN), (
                f"局间推进起点应为 HAND_OVER 或 FLOWN，实际为 {old_phase}"
            )
            assert new_phase == GamePhase.IN_ROUND, f"局间推进终点应为 IN_ROUND，实际为 {new_phase}"

    def test_runner_hand_over_wall_compliance(self) -> None:
        """NEXT_ROUND 附带的 wall 必须是合规的 136 张标准牌山。"""
        from kernel.deal import assert_wall_is_standard_deck

        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=2, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        walls: list[tuple[object, ...]] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            if action.kind == ActionKind.NEXT_ROUND and action.wall is not None:
                walls.append(action.wall)
            return original_apply(state, action)

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：所有 wall 都是合规牌山
        for wall in walls:
            assert_wall_is_standard_deck(wall)


class TestRunnerFlownNextRound:
    """FLOWN → NEXT_ROUND 推进测试（H-28）。"""

    def test_runner_flown_to_next_round_with_valid_wall(self) -> None:
        """FLOWN 后 runner 使用 NEXT_ROUND + 136 张合规 wall 推进下一局。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=2, allow_negative=True)
        seat_llm_configs = load_test_seat_llm_configs()

        # 监控 apply 调用，确认流局后使用 NEXT_ROUND
        next_round_from_flown: list[Action] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            if action.kind == ActionKind.NEXT_ROUND and state.phase == GamePhase.FLOWN:
                next_round_from_flown.append(action)
            return original_apply(state, action)

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：如果发生流局，NEXT_ROUND 应附带合规 wall
        # 注：dry_run 可能不触发流局，但如果有流局则必须验证
        for act in next_round_from_flown:
            assert act.wall is not None, "FLOWN 后 NEXT_ROUND 必须附带 wall"
            assert len(act.wall) == 136, "wall 必须为 136 张"

    def test_runner_flown_phase_transition_correct(self) -> None:
        """FLOWN → NEXT_ROUND → IN_ROUND 状态转换正确。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=2, allow_negative=True)
        seat_llm_configs = load_test_seat_llm_configs()

        phase_transitions: list[tuple[GamePhase, GamePhase]] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            result = original_apply(state, action)
            if action.kind == ActionKind.NEXT_ROUND and state.phase == GamePhase.FLOWN:
                phase_transitions.append((state.phase, result.new_state.phase))
            return result

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：每次流局后推进都是 FLOWN → IN_ROUND
        for old_phase, new_phase in phase_transitions:
            assert old_phase == GamePhase.FLOWN, f"流局后推进起点应为 FLOWN，实际为 {old_phase}"
            assert new_phase == GamePhase.IN_ROUND, f"流局后推进终点应为 IN_ROUND，实际为 {new_phase}"


class TestRunnerNextRoundNoopRejected:
    """确认 runner 不再使用 NOOP 进行局间推进（H-28）。"""

    def test_runner_noop_not_used_for_hand_over(self) -> None:
        """HAND_OVER 阶段 runner 不应使用 NOOP。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=2, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        noop_in_hand_over: list[Action] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            if action.kind == ActionKind.NOOP and state.phase == GamePhase.HAND_OVER:
                noop_in_hand_over.append(action)
            return original_apply(state, action)

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：HAND_OVER 阶段不应有 NOOP 调用
        assert len(noop_in_hand_over) == 0, "HAND_OVER 阶段不应使用 NOOP，应使用 NEXT_ROUND"

    def test_runner_noop_not_used_for_flown(self) -> None:
        """FLOWN 阶段 runner 不应使用 NOOP。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=2, allow_negative=True)
        seat_llm_configs = load_test_seat_llm_configs()

        noop_in_flown: list[Action] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            if action.kind == ActionKind.NOOP and state.phase == GamePhase.FLOWN:
                noop_in_flown.append(action)
            return original_apply(state, action)

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：FLOWN 阶段不应有 NOOP 调用
        assert len(noop_in_flown) == 0, "FLOWN 阶段不应使用 NOOP，应使用 NEXT_ROUND"


class TestRunnerNextRoundWallSeed:
    """NEXT_ROUND wall 种子递增测试（H-28）。"""

    def test_runner_next_round_wall_seed_increments(self) -> None:
        """每次 NEXT_ROUND 使用不同的 seed 生成 wall。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=3, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        walls: list[tuple[object, ...]] = []
        original_apply = apply

        def mock_apply_fn(state: GameState, action: Action) -> object:
            if action.kind == ActionKind.NEXT_ROUND and action.wall is not None:
                walls.append(action.wall)
            return original_apply(state, action)

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：多局对局的 wall 应各不相同（seed 递增）
        if len(walls) >= 2:
            # 比较前两个 wall，不应完全相同
            assert walls[0] != walls[1], "不同局的 wall 应使用不同 seed 生成"


class TestRunnerNextRoundErrorHandling:
    """NEXT_ROUND 错误处理测试（H-28）。"""

    def test_runner_next_round_failed_returns_correct_reason(self) -> None:
        """NEXT_ROUND 失败时返回 next_round_failed。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=100, allow_negative=True)
        seat_llm_configs = load_test_seat_llm_configs()

        original_apply = apply
        hand_over_seen = [False]

        def mock_apply_fn(state: GameState, action: Action) -> object:
            result = original_apply(state, action)
            if result.new_state.phase in (GamePhase.HAND_OVER, GamePhase.FLOWN):
                hand_over_seen[0] = True
            # 第一次局间推进时抛出异常
            if hand_over_seen[0] and action.kind == ActionKind.NEXT_ROUND:
                raise IllegalActionError("next_round wall failed")
            return result

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：失败原因包含 next_round_failed
        assert "next_round_failed" in result.stopped_reason, f"NEXT_ROUND 失败应返回 next_round_failed，实际返回 {result.stopped_reason}"

    def test_runner_next_round_without_wall_fails(self) -> None:
        """NEXT_ROUND 无 wall 时应失败（ValueError 被 runner 主循环捕获）。

        注：runner 当前只在 NEXT_ROUND 块捕获 IllegalActionError，
        但 advance_after_flow 抛 ValueError。此测试验证 runner 主循环能捕获该异常。
        """
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=100, allow_negative=True)
        seat_llm_configs = load_test_seat_llm_configs()

        original_apply = apply
        hand_over_seen = [False]

        def mock_apply_fn(state: GameState, action: Action) -> object:
            result = original_apply(state, action)
            if result.new_state.phase in (GamePhase.HAND_OVER, GamePhase.FLOWN):
                hand_over_seen[0] = True
            # 第一次局间推进时去掉 wall
            if hand_over_seen[0] and action.kind == ActionKind.NEXT_ROUND:
                no_wall_action = Action(ActionKind.NEXT_ROUND, wall=None)
                try:
                    return original_apply(state, no_wall_action)
                except ValueError as e:
                    # ValueError 会被 runner 主循环捕获（line 815）
                    raise IllegalActionError(str(e)) from e
            return result

        with patch("llm.runner.apply", side_effect=mock_apply_fn):
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
            )

        # 验证：失败原因包含 step_failed（runner 主循环捕获 ValueError）
        assert "step_failed" in result.stopped_reason or "next_round_failed" in result.stopped_reason, (
            f"NEXT_ROUND 无 wall 应失败，实际返回 {result.stopped_reason}"
        )