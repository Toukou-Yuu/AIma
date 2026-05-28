"""Tests for MatchRunner orchestration."""

from __future__ import annotations

import pytest

from arena import (
    GameEngine,
    MatchRunner,
    MatchResult,
    InMemorySink,
    IllegalPolicyDecisionError,
)
from policies import FirstLegalPolicy, register_builtin_policies
from experiments.schema import MatchSpec
from kernel import Action, ActionKind


def _make_first_legal_policies() -> dict:
    """创建 4 个 FirstLegalPolicy。"""
    return {i: FirstLegalPolicy(f"seat_{i}") for i in range(4)}


register_builtin_policies()


class TestMatchRunner:
    """MatchRunner 核心逻辑测试。"""

    def test_four_first_legal_complete_tonpuu(self) -> None:
        """4 个 FirstLegalPolicy 可跑完 tonpuu。

        注意：由于 tonpuu 可能因九九种等特殊流局而在 max_hands 截断前未达到自然终局，
        stopped_reason 可能是 'max_hands_reached' 而非 None。
        """
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec(preset="tonpuu")
        result = runner.run(spec, seed=42)

        assert result.step_count > 0
        # 接受自然终局或截断两种情况
        assert result.outcome in ("completed", "truncated")
        if result.outcome == "completed":
            assert result.stopped_reason is None
        else:
            assert result.stopped_reason in ("max_hands_reached", "step_limit_exceeded")

    def test_step_limit_enforced(self) -> None:
        """step_limit 生效。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies, step_limit=20)

        spec = MatchSpec()
        result = runner.run(spec, seed=42)

        assert result.step_count <= 20

    def test_sink_on_step_called(self) -> None:
        """InMemorySink 收集 decisions。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        sink = InMemorySink()
        runner = MatchRunner(engine, policies, sinks=[sink])

        spec = MatchSpec(preset="tonpuu")
        result = runner.run(spec, seed=42)

        # sink.decisions 只收集 Policy.decide() 的决策，不包括 BEGIN_ROUND/NEXT_ROUND
        assert len(sink.decisions) == len(result.decisions)

    def test_match_result_fields(self) -> None:
        """MatchResult 包含必需字段。"""
        engine = GameEngine()
        policies = _make_first_legal_policies()
        runner = MatchRunner(engine, policies)

        spec = MatchSpec()
        result = runner.run(spec, seed=42)

        assert result.match_id is not None
        assert result.seed == 42
        assert result.step_count > 0


class TestMatchRunnerIllegalAction:
    """非法 action 处理测试。"""

    def test_illegal_action_raises(self) -> None:
        """非法 action 抛出 IllegalPolicyDecisionError。"""
        # 构造返回非法 action 的 Policy
        class BadPolicy:
            name = "bad"
            policy_id = "bad"
            def decide(self, ctx):
                return type("D", (), {"action": Action(ActionKind.DRAW, seat=99)})()

        engine = GameEngine()
        policies = {0: BadPolicy(), 1: FirstLegalPolicy("s1"),
                    2: FirstLegalPolicy("s2"), 3: FirstLegalPolicy("s3")}
        runner = MatchRunner(engine, policies)

        spec = MatchSpec()
        with pytest.raises(IllegalPolicyDecisionError):
            runner.run(spec, seed=42)