"""MatchSpec语义测试 - 验证max_hands/step_limit的正确行为。

测试用例：
1. tonpuu + max_hands=None/default → completed, match_end, hand_count=4
2. tonpuu + max_hands=1 → truncated, stopped_reason=max_hands_reached, hand_count=1
3. hanchan + max_hands=None/default → completed, match_end, hand_count=8
4. hanchan + max_hands=2 → truncated, stopped_reason=max_hands_reached, hand_count=2
5. step_limit=10 → outcome=step_limit_reached, stopped_reason=step_limit_exceeded
"""

from __future__ import annotations

import pytest

from arena import GameEngine, MatchRunner
from experiments.schema import MatchSpec
from policies import FirstLegalPolicy, register_builtin_policies

register_builtin_policies()


def _make_first_legal_policies() -> dict[int, FirstLegalPolicy]:
    """创建 4 个 FirstLegalPolicy。"""
    return {i: FirstLegalPolicy(f"seat_{i}") for i in range(4)}


class TestMatchSpecSemantics:
    """验证MatchSpec的max_hands/step_limit语义正确性。"""

    def test_tonpuu_default_max_hands(self) -> None:
        """tonpuu + max_hands=None → completed, match_end, hand_count=4。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="tonpuu")  # max_hands=None
        result = runner.run(spec, seed=42)

        assert result.outcome == "completed", f"outcome应为completed，实际为{result.outcome}"
        assert result.final_phase == "match_end", f"final_phase应为match_end，实际为{result.final_phase}"
        assert result.hand_count == 4, f"hand_count应为4，实际为{result.hand_count}"

    def test_tonpuu_max_hands_1(self) -> None:
        """tonpuu + max_hands=1 → truncated, stopped_reason=max_hands_reached, hand_count=1。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="tonpuu", max_hands=1)
        result = runner.run(spec, seed=42)

        assert result.outcome == "truncated", f"outcome应为truncated，实际为{result.outcome}"
        assert result.stopped_reason == "max_hands_reached", (
            f"stopped_reason应为max_hands_reached，实际为{result.stopped_reason}"
        )
        assert result.hand_count == 1, f"hand_count应为1，实际为{result.hand_count}"

    def test_hanchan_default_max_hands(self) -> None:
        """hanchan + max_hands=None → completed, match_end, hand_count=8。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="hanchan")  # max_hands=None
        result = runner.run(spec, seed=42)

        assert result.outcome == "completed", f"outcome应为completed，实际为{result.outcome}"
        assert result.final_phase == "match_end", f"final_phase应为match_end，实际为{result.final_phase}"
        assert result.hand_count == 8, f"hand_count应为8，实际为{result.hand_count}"

    def test_hanchan_max_hands_2(self) -> None:
        """hanchan + max_hands=2 → truncated, stopped_reason=max_hands_reached, hand_count=2。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="hanchan", max_hands=2)
        result = runner.run(spec, seed=42)

        assert result.outcome == "truncated", f"outcome应为truncated，实际为{result.outcome}"
        assert result.stopped_reason == "max_hands_reached", (
            f"stopped_reason应为max_hands_reached，实际为{result.stopped_reason}"
        )
        assert result.hand_count == 2, f"hand_count应为2，实际为{result.hand_count}"

    def test_step_limit_reached(self) -> None:
        """step_limit=10 → outcome=step_limit_reached, stopped_reason=step_limit_exceeded。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies, step_limit=10)

        spec = MatchSpec(preset="tonpuu")  # max_hands=None (default 4)
        result = runner.run(spec, seed=42)

        assert result.outcome == "step_limit_reached", (
            f"outcome应为step_limit_reached，实际为{result.outcome}"
        )
        assert result.stopped_reason == "step_limit_exceeded", (
            f"stopped_reason应为step_limit_exceeded，实际为{result.stopped_reason}"
        )

    def test_tonpuu_max_hands_greater_than_natural(self) -> None:
        """tonpuu + max_hands=10 → completed, hand_count=4（自然终局）。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="tonpuu", max_hands=10)
        result = runner.run(spec, seed=42)

        assert result.outcome == "completed", f"outcome应为completed，实际为{result.outcome}"
        assert result.hand_count == 4, f"hand_count应为4，实际为{result.hand_count}"

    def test_hanchan_max_hands_greater_than_natural(self) -> None:
        """hanchan + max_hands=16 → completed, hand_count=8（自然终局）。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="hanchan", max_hands=16)
        result = runner.run(spec, seed=42)

        assert result.outcome == "completed", f"outcome应为completed，实际为{result.outcome}"
        assert result.hand_count == 8, f"hand_count应为8，实际为{result.hand_count}"


class TestMatchSpecStepLimit:
    """验证step_limit语义正确性。"""

    def test_step_limit_from_spec(self) -> None:
        """step_limit应来自spec.step_limit。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()

        # 使用spec中的step_limit
        runner = MatchRunner(engine, policies)  # 不指定step_limit
        spec = MatchSpec(preset="tonpuu", step_limit=10)
        result = runner.run(spec, seed=42)

        assert result.outcome == "step_limit_reached", (
            f"outcome应为step_limit_reached，实际为{result.outcome}"
        )

    def test_step_limit_from_runner_constructor(self) -> None:
        """runner构造参数的step_limit应覆盖spec.step_limit。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()

        # runner构造参数优先
        runner = MatchRunner(engine, policies, step_limit=10)
        spec = MatchSpec(preset="tonpuu", step_limit=20000)  # spec中很大的step_limit
        result = runner.run(spec, seed=42)

        assert result.outcome == "step_limit_reached", (
            f"outcome应为step_limit_reached，实际为{result.outcome}"
        )