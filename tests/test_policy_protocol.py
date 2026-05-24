"""Tests for Policy Protocol compliance."""

from __future__ import annotations

import pytest

from arena import Policy, DecisionContext, PolicyDecision
from policies import FirstLegalPolicy, RandomPolicy, FixedHeuristicPolicy


class TestPolicyProtocol:
    """验证 Policy Protocol 定义正确，各策略实现符合协议。"""

    def test_first_legal_policy_has_name(self) -> None:
        """FirstLegalPolicy 有 name 属性。"""
        p = FirstLegalPolicy("test")
        assert p.name == "first_legal"

    def test_first_legal_policy_has_policy_id(self) -> None:
        """FirstLegalPolicy 有 policy_id 属性。"""
        p = FirstLegalPolicy("test_001")
        assert p.policy_id == "test_001"

    def test_first_legal_policy_has_decide(self) -> None:
        """FirstLegalPolicy 有 decide 方法。"""
        p = FirstLegalPolicy("test")
        assert hasattr(p, "decide")
        assert callable(p.decide)

    def test_random_policy_has_name(self) -> None:
        """RandomPolicy 有 name 属性。"""
        p = RandomPolicy("test", seed=42)
        assert p.name == "random"

    def test_fixed_heuristic_policy_has_name(self) -> None:
        """FixedHeuristicPolicy 有 name 属性。"""
        p = FixedHeuristicPolicy("test")
        assert p.name == "fixed_heuristic"


class TestPolicyDecisionFrozen:
    """验证 PolicyDecision 是 frozen dataclass。"""

    def test_policy_decision_frozen(self) -> None:
        """PolicyDecision 不能修改。"""
        from kernel.engine.actions import Action, ActionKind
        dec = PolicyDecision(action=Action(ActionKind.NOOP))
        with pytest.raises(AttributeError):
            dec.parse_status = "error"  # type: ignore[misc]


class TestDecisionContext:
    """验证 DecisionContext 结构。"""

    def test_decision_context_has_required_fields(self) -> None:
        """DecisionContext 包含必需字段。"""
        # 仅验证字段存在，不验证类型
        ctx = DecisionContext.__dataclass_fields__
        required = ["match_id", "job_id", "hand_index", "step_index", "seed",
                    "seat", "phase", "state", "observation", "legal_actions"]
        for field in required:
            assert field in ctx