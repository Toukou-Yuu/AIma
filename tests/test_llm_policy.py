"""Tests for LLMPolicy Protocol compliance and DummyBackend integration."""

from __future__ import annotations

import pytest

from arena import GameEngine
from kernel import Action, ActionKind, build_deck, shuffle_deck
from kernel.engine.state import initial_game_state
from kernel.api.legal_actions import LegalAction
from kernel.tiles.model import Suit, Tile

from policies.llm_policy import LLMPolicy
from llm.adapters.dummy import DummyBackend
from agents.schema import AgentSpec


def _wall136(seed: int = 0) -> tuple:
    return tuple(shuffle_deck(build_deck(), seed=seed))


def _make_decision_context() -> "DecisionContext":
    """Create a minimal DecisionContext for testing."""
    from arena.policy import DecisionContext

    engine = GameEngine()
    g0 = initial_game_state()
    w = _wall136(42)

    from kernel import apply
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state

    return DecisionContext(
        match_id="test_match",
        job_id="test_job",
        hand_index=0,
        step_index=0,
        seed=42,
        seat=0,
        phase="in_round",
        state=g1,
        observation=engine.observe(g1, 0),
        legal_actions=engine.legal_actions(g1, 0),
    )


def _make_agent_spec(fallback: str = "first_legal") -> AgentSpec:
    """Create a minimal AgentSpec for testing."""
    from prompts.schema import PromptSpec
    from models.schema import ModelSpec

    # 使用现有的模板 riichi_json_action_v1
    return AgentSpec(
        pipeline_id="test_pipeline",
        prompt=PromptSpec(
            template_id="riichi_json_action_v1",
            version="1.0.0",
            sections=[],  # 使用模板默认 sections
        ),
        model=ModelSpec(backend="dummy", model_name="test-model"),
        fallback=fallback,
    )


class TestLLMPolicyProtocol:
    """Verify LLMPolicy implements Policy Protocol correctly."""

    def test_llm_policy_has_name(self) -> None:
        """LLMPolicy has 'name' attribute."""
        backend = DummyBackend(response='{"kind":"draw","seat":0}')
        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)
        assert policy.name == "llm"

    def test_llm_policy_has_policy_id(self) -> None:
        """LLMPolicy has 'policy_id' attribute."""
        backend = DummyBackend(response='{"kind":"draw","seat":0}')
        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test_policy_001", spec=spec, seed=42, client=backend)
        assert policy.policy_id == "test_policy_001"

    def test_llm_policy_has_decide(self) -> None:
        """LLMPolicy has callable 'decide' method."""
        backend = DummyBackend(response='{"kind":"draw","seat":0}')
        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)
        assert hasattr(policy, "decide")
        assert callable(policy.decide)

    def test_llm_policy_decide_returns_policy_decision(self) -> None:
        """LLMPolicy.decide() returns PolicyDecision instance."""
        from arena.policy import PolicyDecision

        backend = DummyBackend(response='{"kind":"draw","seat":0}')
        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)
        ctx = _make_decision_context()

        decision = policy.decide(ctx)
        assert isinstance(decision, PolicyDecision)


class TestLLMPolicyWithDummyBackend:
    """AC1: DummyBackend + LLMPolicy outputs legal action."""

    def test_dummy_backend_returns_legal_action(self) -> None:
        """AC1: DummyBackend + LLMPolicy returns legal action."""
        ctx = _make_decision_context()

        # Use matching response - game state has DISCARD actions
        first_action = ctx.legal_actions[0]
        tile_code = first_action.tile.to_code() if first_action.tile else "1m"
        backend = DummyBackend(response=f'{{"kind":"discard","seat":0,"tile":"{tile_code}"}}')

        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)

        decision = policy.decide(ctx)
        assert decision.action is not None
        assert decision.action.kind == first_action.kind  # Should match DISCARD

    def test_dummy_backend_ignores_input(self) -> None:
        """DummyBackend ignores prompt, returns pre-configured response."""
        ctx = _make_decision_context()

        first_action = ctx.legal_actions[0]
        tile_code = first_action.tile.to_code() if first_action.tile else "1m"
        backend = DummyBackend(response=f'{{"kind":"discard","seat":0,"tile":"{tile_code}"}}')

        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)

        # First call
        decision1 = policy.decide(ctx)
        assert decision1.action.kind == first_action.kind

        # Change backend response to something that doesn't match -> fallback
        backend.response = '{"kind":"tsumo","seat":0}'
        decision2 = policy.decide(ctx)
        # Should use fallback
        assert decision2.fallback_used is True

    def test_llm_policy_uses_backend_output(self) -> None:
        """LLMPolicy correctly uses Backend output."""
        ctx = _make_decision_context()

        first_action = ctx.legal_actions[0]
        tile_code = first_action.tile.to_code() if first_action.tile else "1m"
        backend = DummyBackend(response=f'{{"kind":"discard","seat":0,"tile":"{tile_code}"}}')

        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)

        decision = policy.decide(ctx)
        assert tile_code in decision.raw_output


class TestLLMPolicyFallbackBehavior:
    """AC2-AC5: Verify fallback behavior is correctly recorded."""

    def test_parse_failed_recorded(self) -> None:
        """AC2: Non-JSON output recorded as parse_failed."""
        backend = DummyBackend(response="not json at all")
        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)
        ctx = _make_decision_context()

        decision = policy.decide(ctx)
        assert decision.parse_status == "parse_failed"
        assert decision.fallback_used is True

    def test_match_failed_recorded(self) -> None:
        """AC3: Illegal action recorded as match_failed."""
        backend = DummyBackend(response='{"kind":"tsumo","seat":0}')
        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)
        ctx = _make_decision_context()

        decision = policy.decide(ctx)
        assert decision.parse_status == "match_failed"
        assert decision.fallback_used is True

    def test_fallback_used_in_trace(self) -> None:
        """AC4: fallback_used correctly recorded in PolicyDecision."""
        backend = DummyBackend(response="invalid json")
        spec = _make_agent_spec()
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)
        ctx = _make_decision_context()

        decision = policy.decide(ctx)
        # fallback_used should be True since parse failed
        assert decision.fallback_used is True
        # diagnostics should record fallback_used
        assert decision.diagnostics.get("fallback_used") is True

    def test_first_legal_fallback_triggers(self) -> None:
        """AC5: first_legal fallback correctly triggers."""
        backend = DummyBackend(response="invalid json")
        spec = _make_agent_spec(fallback="first_legal")
        policy = LLMPolicy(policy_id="test", spec=spec, seed=42, client=backend)
        ctx = _make_decision_context()

        decision = policy.decide(ctx)
        assert decision.fallback_used is True
        assert decision.action is not None
        # first_legal should return legal_actions[0]
        expected_action = ctx.legal_actions[0]
        assert decision.action.kind == expected_action.kind


class TestDummyBackend:
    """Verify DummyBackend test utility."""

    def test_dummy_backend_configurable_response(self) -> None:
        """DummyBackend can be configured with any response string."""
        backend1 = DummyBackend(response="response 1")
        backend2 = DummyBackend(response="response 2")

        assert backend1.response == "response 1"
        assert backend2.response == "response 2"

    def test_dummy_backend_response_setter(self) -> None:
        """DummyBackend response can be changed after creation."""
        backend = DummyBackend(response="initial")
        assert backend.response == "initial"

        backend.response = "changed"
        assert backend.response == "changed"

    def test_dummy_backend_complete_returns_response(self) -> None:
        """DummyBackend.complete() returns pre-configured response."""
        from llm.protocol import ChatMessage

        backend = DummyBackend(response="test response")
        messages = [ChatMessage(role="user", content="any prompt")]
        result = backend.complete(messages)
        assert result == "test response"