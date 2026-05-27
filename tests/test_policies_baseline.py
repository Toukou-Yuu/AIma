"""Tests for baseline policies."""

from __future__ import annotations

import pytest

from arena import DecisionContext, GameEngine
from kernel import Action, ActionKind, build_deck, shuffle_deck
from kernel.engine.state import initial_game_state
from policies import (
    REGISTRY,
    FirstLegalPolicy,
    FixedHeuristicPolicy,
    RandomPolicy,
    legal_action_to_action,
    register_builtin_policies,
)
from policies.registry import PolicyFactoryContext, PolicyRegistry
from policies.schema import PolicySpec


def _wall136(seed: int = 0) -> tuple:
    return tuple(shuffle_deck(build_deck(), seed=seed))


class TestFirstLegalPolicy:
    """FirstLegalPolicy 测试。"""

    def test_returns_first_legal_action(self) -> None:
        """FirstLegalPolicy 返回 legal_actions[0] 对应的 Action。"""
        engine = GameEngine()
        g0 = initial_game_state()
        w = _wall136(10)

        from kernel import apply
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        legal = engine.legal_actions(g1, 0)
        assert len(legal) > 0

        policy = FirstLegalPolicy("test")
        ctx = DecisionContext(
            match_id="test",
            job_id="test",
            hand_index=0,
            step_index=0,
            seed=42,
            seat=0,
            phase="in_round",
            state=g1,
            observation=engine.observe(g1, 0),
            legal_actions=legal,
        )
        dec = policy.decide(ctx)

        expected = legal_action_to_action(legal[0])
        assert dec.action == expected


class TestRandomPolicy:
    """RandomPolicy 测试。"""

    def test_deterministic_with_seed(self) -> None:
        """RandomPolicy 使用 seed，结果确定。"""
        engine = GameEngine()
        g0 = initial_game_state()
        w = _wall136(10)

        from kernel import apply
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        legal = engine.legal_actions(g1, 0)

        # 同 seed 两次 decide，选择一致
        p1 = RandomPolicy("r1", seed=100)
        p2 = RandomPolicy("r2", seed=100)

        ctx = DecisionContext(
            match_id="test", job_id="test", hand_index=0, step_index=0,
            seed=42, seat=0, phase="in_round", state=g1,
            observation=engine.observe(g1, 0), legal_actions=legal,
        )

        d1 = p1.decide(ctx)
        d2 = p2.decide(ctx)

        assert d1.action == d2.action


class TestFixedHeuristicPolicy:
    """FixedHeuristicPolicy 测试。"""

    def test_prioritizes_tsumo(self) -> None:
        """FixedHeuristicPolicy 优先自摸。"""
        from kernel.api.legal_actions import LegalAction

        engine = GameEngine()
        g0 = initial_game_state()
        w = _wall136(10)

        from kernel import apply
        g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

        legal = (
            LegalAction(ActionKind.DISCARD, seat=0),
            LegalAction(ActionKind.TSUMO, seat=0),
        )

        p = FixedHeuristicPolicy("test")

        decision = p.decide(
            DecisionContext(
                match_id="test",
                job_id="test",
                hand_index=0,
                step_index=0,
                seed=42,
                seat=0,
                phase="in_round",
                state=g1,
                observation=engine.observe(g1, 0),
                legal_actions=legal,
            )
        )

        assert decision.action.kind == ActionKind.TSUMO
        # 验证 TSUMO 的优先级数值更高
        from policies.fixed_heuristic_policy import ACTION_PRIORITY

        assert ACTION_PRIORITY[ActionKind.TSUMO] > ACTION_PRIORITY[ActionKind.DISCARD]


class TestPolicyRegistry:
    """PolicyRegistry 测试。"""

    def test_registry_has_builtin_types(self) -> None:
        """Registry 注册了 builtin policies。"""
        register_builtin_policies()

        assert "first_legal" in REGISTRY._factories
        assert "random" in REGISTRY._factories
        assert "fixed_heuristic" in REGISTRY._factories

    def test_registry_creates_first_legal(self) -> None:
        """Registry 可创建 FirstLegalPolicy。"""
        register_builtin_policies()

        spec = PolicySpec(type="first_legal", id="test")
        p = REGISTRY.create(spec, PolicyFactoryContext(seed=42))

        assert isinstance(p, FirstLegalPolicy)

    def test_registry_context_factory_receives_runtime_context(self) -> None:
        """Factories receive the full runtime context."""
        registry = PolicyRegistry()
        captured_context: dict[str, PolicyFactoryContext] = {}

        def factory(spec: PolicySpec, ctx: PolicyFactoryContext) -> FirstLegalPolicy:
            captured_context["value"] = ctx
            return FirstLegalPolicy(spec.id)

        context = PolicyFactoryContext(seed=7, memory_enabled=False)
        registry.register("first_legal", factory)
        spec = PolicySpec(type="first_legal", id="context")
        p = registry.create(spec, context)

        assert isinstance(p, FirstLegalPolicy)
        assert captured_context["value"] is context

    def test_registry_unknown_type_raises(self) -> None:
        """PolicySpec 对未知 type，Pydantic 校验抛出 ValidationError。"""
        from pydantic import ValidationError

        register_builtin_policies()

        # PolicySpec 使用 Literal 类型，创建时即校验
        with pytest.raises(ValidationError):
            PolicySpec(type="unknown", id="test")
