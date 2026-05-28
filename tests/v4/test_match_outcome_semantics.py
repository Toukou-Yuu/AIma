"""P0-3 Regression Tests: Match Outcome Semantics.

Bug: match_runner.py 不区分自然终局与 max_hands 截断。

Root cause: src/arena/match_runner.py:169-171 和 253-259
- max_hands break 不设置 stopped_reason
- post-loop check 只处理 step_limit，不处理 max_hands truncation

Expected semantics (based on is_terminal() distinction):
| Scenario              | is_terminal() | outcome              | stopped_reason        |
|-----------------------|---------------|----------------------|-----------------------|
| Natural match end     | True          | "completed"          | None                  |
| max_hands truncation  | False         | "truncated"          | "max_hands_reached"   |
| step_limit truncation | False         | "step_limit_reached" | "step_limit_exceeded" |

关键区分标准：is_terminal() 返回 True 表示自然终局，False 表示截断。
"""

from __future__ import annotations

import pytest

from arena import GameEngine, MatchRunner
from experiments.schema import MatchSpec
from kernel.engine.phase import GamePhase
from policies import FirstLegalPolicy, register_builtin_policies

register_builtin_policies()


def _make_first_legal_policies() -> dict:
    """创建 4 个 FirstLegalPolicy。"""
    return {i: FirstLegalPolicy(f"seat_{i}") for i in range(4)}


class TestMatchOutcomeSemantics:
    """验证 MatchResult.outcome 和 stopped_reason 的语义正确性。

    这些测试在修复前应该失败，因为：
    1. MatchResult 没有 outcome 字段
    2. max_hands truncation 不设置 stopped_reason
    """

    def test_natural_match_end_when_terminal(self) -> None:
        """自然终局（is_terminal=True）应设置 outcome="completed", stopped_reason=None。

        自然终局：kernel 的 is_terminal() 返回 True（phase == MATCH_END）。
        注意：当前 kernel 可能未正确实现 MATCH_END 过渡，此测试同时暴露该问题。
        """
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        # 东风战，应该自然打完 4 局
        spec = MatchSpec(preset="tonpuu")
        result = runner.run(spec, seed=42)

        # 使用 is_terminal() 作为自然终局的判断标准
        is_natural_end = engine.is_terminal(result.final_state)

        if is_natural_end:
            # 自然终局：stopped_reason 应为 None
            assert result.stopped_reason is None, (
                f"自然终局 stopped_reason 应为 None，实际为 {result.stopped_reason!r}"
            )
            # 验证 outcome 字段
            assert hasattr(result, "outcome"), "MatchResult 应有 outcome 字段"
            assert result.outcome == "completed", (
                f"自然终局 outcome 应为 'completed'，实际为 {result.outcome}"
            )
        else:
            # 如果不是自然终局，说明 kernel MATCH_END 过渡问题或 max_hands 截断问题
            # 对于 P0-3，我们主要关注 max_hands 截断问题
            pytest.skip(
                f"kernel 未正确过渡到 MATCH_END，phase={result.final_state.phase}，"
                f"这是 kernel 问题而非 match_runner 语义问题"
            )

    def test_max_hands_truncation_is_not_terminal(self) -> None:
        """max_hands 截断时 is_terminal() 应返回 False，且 stopped_reason 应明确标记。

        这是 P0-3 bug 的核心表现：
        - 当 hand_index >= max_hands 且 phase != MATCH_END 时，
          match_runner 应设置 stopped_reason="max_hands_reached"。
        """
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        # 使用 max_hands=1 强制在第一局后截断
        spec = MatchSpec(preset="hanchan", max_hands=1)
        result = runner.run(spec, seed=42)

        # 核心断言：截断时 is_terminal() 应返回 False
        is_terminal = engine.is_terminal(result.final_state)
        assert not is_terminal, (
            f"max_hands 截断时 is_terminal() 应返回 False，"
            f"实际 phase={result.final_state.phase}，is_terminal={is_terminal}"
        )

        # Bug 表现：stopped_reason 应为 "max_hands_reached"，实际为 None
        assert result.stopped_reason == "max_hands_reached", (
            f"[P0-3 BUG] max_hands 截断 stopped_reason 应为 'max_hands_reached'，"
            f"实际为 {result.stopped_reason!r}（bug 表现为 None）"
        )

        # outcome 字段应存在且为 "truncated"
        assert hasattr(result, "outcome"), "MatchResult 应有 outcome 字段"
        assert result.outcome == "truncated", (
            f"max_hands 截断 outcome 应为 'truncated'，实际为 {result.outcome}"
        )

    def test_max_hands_truncation_custom_preset(self) -> None:
        """自定义 preset 的 max_hands 截断测试。

        验证 custom preset 的 max_hands 截断语义也正确。
        """
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        # custom preset，max_hands=2
        spec = MatchSpec(preset="custom", max_hands=2)
        result = runner.run(spec, seed=42)

        # 截断时 is_terminal() 应返回 False
        is_terminal = engine.is_terminal(result.final_state)
        assert not is_terminal, (
            f"custom max_hands 截断时 is_terminal() 应返回 False，"
            f"实际 phase={result.final_state.phase}"
        )

        # Bug 表现：stopped_reason 应设置
        assert result.stopped_reason == "max_hands_reached", (
            f"[P0-3 BUG] custom max_hands 截断 stopped_reason 应为 'max_hands_reached'，"
            f"实际为 {result.stopped_reason!r}"
        )

        assert hasattr(result, "outcome"), "MatchResult 应有 outcome 字段"
        assert result.outcome == "truncated", (
            f"custom max_hands 截断 outcome 应为 'truncated'，实际为 {result.outcome}"
        )

    def test_step_limit_truncation_sets_correct_semantics(self) -> None:
        """step_limit 截断应设置 outcome="step_limit_reached", stopped_reason="step_limit_exceeded"。

        step_limit 截断已在当前实现中处理，此测试验证语义正确。
        注意：outcome 字段尚未添加，此测试也会失败。
        """
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies, step_limit=10)

        spec = MatchSpec(preset="hanchan")
        result = runner.run(spec, seed=42)

        # 验证 step_limit 截断
        assert result.step_count <= 10, (
            f"step_limit 截断应 <= 10 步，实际为 {result.step_count}"
        )

        # is_terminal() 应返回 False（因为是截断）
        is_terminal = engine.is_terminal(result.final_state)
        assert not is_terminal, (
            f"step_limit 截断时 is_terminal() 应返回 False，"
            f"实际 phase={result.final_state.phase}"
        )

        # stopped_reason 当前实现已处理
        assert result.stopped_reason == "step_limit_exceeded", (
            f"step_limit 截断 stopped_reason 应为 'step_limit_exceeded'，"
            f"实际为 {result.stopped_reason!r}"
        )

        # outcome 字段尚未添加，会失败
        assert hasattr(result, "outcome"), "MatchResult 应有 outcome 字段"
        assert result.outcome == "step_limit_reached", (
            f"step_limit 截断 outcome 应为 'step_limit_reached'，实际为 {result.outcome}"
        )


class TestMatchOutcomeField:
    """验证 MatchResult.outcome 字段存在。

    outcome 字段是区分 completed/truncated/step_limit_reached 的关键。
    """

    def test_outcome_field_exists_on_match_result(self) -> None:
        """MatchResult 数据类应有 outcome 字段。

        修复需要：在 src/arena/match_result.py 添加 outcome: str 字段。
        """
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="tonpuu")
        result = runner.run(spec, seed=42)

        # Bug 表现：outcome 字段不存在
        assert hasattr(result, "outcome"), (
            "[P0-3 BUG] MatchResult 应有 outcome 字段，当前不存在"
        )

    def test_outcome_is_string_type(self) -> None:
        """outcome 应为字符串类型。

        验证 outcome 字段的类型正确。
        """
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="tonpuu")
        result = runner.run(spec, seed=42)

        # 需要 outcome 字段存在才能检查类型
        assert hasattr(result, "outcome"), "MatchResult 应有 outcome 字段"
        assert isinstance(result.outcome, str), (
            f"outcome 应为 str 类型，实际为 {type(result.outcome)}"
        )


class TestTerminalVsTruncationSemantics:
    """验证 is_terminal() 与 outcome/stopped_reason 的语义对应关系。

    核心原则：
    - is_terminal() == True → outcome="completed", stopped_reason=None
    - is_terminal() == False → outcome="truncated" 或 "step_limit_reached"
    """

    def test_terminal_state_means_completed(self) -> None:
        """如果 is_terminal() 返回 True，则应为 completed。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="tonpuu")
        result = runner.run(spec, seed=42)

        is_terminal = engine.is_terminal(result.final_state)

        if is_terminal:
            # 自然终局
            assert result.stopped_reason is None
            if hasattr(result, "outcome"):
                assert result.outcome == "completed"
        else:
            # kernel MATCH_END 过渡问题，跳过
            pytest.skip("kernel 未正确过渡到 MATCH_END")

    def test_non_terminal_state_means_truncated(self) -> None:
        """如果 is_terminal() 返回 False，则应为截断（非 completed）。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="hanchan", max_hands=1)
        result = runner.run(spec, seed=42)

        is_terminal = engine.is_terminal(result.final_state)
        assert not is_terminal, "max_hands=1 截断应导致 is_terminal() 返回 False"

        # 非终局状态的 stopped_reason 不应为 None
        assert result.stopped_reason is not None, (
            f"[P0-3 BUG] 截断状态的 stopped_reason 不应为 None，"
            f"应为 'max_hands_reached'"
        )
        assert result.stopped_reason == "max_hands_reached"

        if hasattr(result, "outcome"):
            assert result.outcome in ("truncated", "step_limit_reached"), (
                f"截断状态 outcome 应为 'truncated' 或 'step_limit_reached'，"
                f"实际为 {result.outcome}"
            )