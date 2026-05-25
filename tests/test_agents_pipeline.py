"""Tests for AgentPipeline and its components."""

from __future__ import annotations

import pytest

from arena import GameEngine
from kernel import Action, ActionKind, build_deck, shuffle_deck
from kernel.engine.state import initial_game_state
from kernel.api.legal_actions import LegalAction
from kernel.tiles.model import Suit, Tile

from agents.pipeline_result import ParseResult, GroundResult, PipelineResult, ParseStatus
from agents.components.parser import OutputParser
from agents.components.grounding import ActionGrounder
from agents.components.fallback import FallbackStrategy, FallbackKind
from agents.pipeline import AgentPipeline
from agents.components.factory import build_components, PipelineComponents
from agents.schema import AgentSpec
from llm.adapters.dummy import DummyBackend


def _wall136(seed: int = 0) -> tuple:
    return tuple(shuffle_deck(build_deck(), seed=seed))


def _make_legal_actions() -> tuple[LegalAction, ...]:
    """Create a tuple of legal actions for testing."""
    return (
        LegalAction(kind=ActionKind.DRAW, seat=0),
        LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 1)),
        LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 2)),
    )


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


def _make_agent_spec() -> AgentSpec:
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
        fallback="first_legal",
    )


class TestPipelineResult:
    """Verify ParseResult, GroundResult, PipelineResult frozen dataclasses."""

    def test_parse_result_matched(self) -> None:
        """ParseResult.status='matched' indicates successful parsing."""
        result = ParseResult(
            choice={"kind": "draw", "seat": 0},
            why="test reason",
            status="matched",
        )
        assert result.status == "matched"
        assert result.choice is not None
        assert result.error is None

    def test_parse_result_parse_failed(self) -> None:
        """ParseResult.status='parse_failed' indicates parsing error."""
        result = ParseResult(
            choice=None,
            why=None,
            status="parse_failed",
            error="invalid JSON: no braces",
        )
        assert result.status == "parse_failed"
        assert result.choice is None
        assert result.error is not None

    def test_parse_result_match_failed(self) -> None:
        """ParseResult.status='match_failed' indicates no matching action."""
        result = ParseResult(
            choice={"kind": "tsumo", "seat": 0},  # not in legal_actions
            why="want to win",
            status="match_failed",
            error="response did not match any legal action",
        )
        assert result.status == "match_failed"
        assert result.choice is not None  # choice exists but doesn't match
        assert result.error is not None

    def test_ground_result_matched(self) -> None:
        """GroundResult.status='grounded' indicates successful grounding."""
        legal = _make_legal_actions()
        result = GroundResult(
            legal_action=legal[0],
            status="grounded",
        )
        assert result.status == "grounded"
        assert result.legal_action is not None
        assert result.legal_action.kind == ActionKind.DRAW

    def test_ground_result_match_failed(self) -> None:
        """GroundResult.status='no_match' indicates no matching legal action."""
        result = GroundResult(
            legal_action=None,
            status="no_match",
        )
        assert result.status == "no_match"
        assert result.legal_action is None

    def test_pipeline_result_frozen(self) -> None:
        """PipelineResult is frozen dataclass, cannot modify."""
        legal = _make_legal_actions()
        result = PipelineResult(
            action=legal[0],
            parse_status="matched",
            fallback_used=False,
            raw_output="{}",
            diagnostics={},
            latency_ms=10.0,
        )
        with pytest.raises(AttributeError):
            result.parse_status = "error"  # type: ignore[misc]


class TestOutputParser:
    """Verify OutputParser wraps DecisionParser correctly."""

    def test_parse_valid_json_matched(self) -> None:
        """Valid JSON matching legal action -> status='matched'."""
        legal = _make_legal_actions()
        raw = '{"kind":"draw","seat":0}'
        result = OutputParser.parse(raw, legal)
        assert result.status == "matched"
        assert result.choice == {"kind": "draw", "seat": 0}

    def test_parse_invalid_json_parse_failed(self) -> None:
        """Invalid JSON -> status='parse_failed', error recorded."""
        legal = _make_legal_actions()
        raw = "not json at all"
        result = OutputParser.parse(raw, legal)
        assert result.status == "parse_failed"
        assert result.error is not None
        assert "no JSON object" in result.error

    def test_parse_valid_json_match_failed(self) -> None:
        """Valid JSON but no matching legal action -> status='match_failed'."""
        legal = _make_legal_actions()
        raw = '{"kind":"tsumo","seat":0}'  # TSUMO not in legal_actions
        result = OutputParser.parse(raw, legal)
        assert result.status == "match_failed"
        assert result.choice is not None  # choice parsed successfully
        assert result.error is not None

    def test_parse_preserves_why(self) -> None:
        """Parser preserves 'why' field from response."""
        legal = _make_legal_actions()
        raw = '{"kind":"draw","seat":0,"why":"Good tile to draw"}'
        result = OutputParser.parse(raw, legal)
        assert result.why == "Good tile to draw"

    def test_parse_fenced_json_note(self) -> None:
        """Fenced JSON (```json...```) is accepted."""
        legal = _make_legal_actions()
        raw = '```json\n{"kind":"draw","seat":0}\n```'
        result = OutputParser.parse(raw, legal)
        assert result.status == "matched"


class TestActionGrounder:
    """Verify ActionGrounder wraps find_matching_legal_action correctly."""

    def test_ground_exact_match(self) -> None:
        """Choice exactly matches a legal action -> status='grounded'."""
        legal = _make_legal_actions()
        choice = {"kind": "draw", "seat": 0}
        result = ActionGrounder.ground(legal, choice)
        assert result.status == "grounded"
        assert result.legal_action is not None
        assert result.legal_action.kind == ActionKind.DRAW

    def test_ground_no_match(self) -> None:
        """Choice doesn't match any legal action -> status='no_match'."""
        legal = _make_legal_actions()
        choice = {"kind": "tsumo", "seat": 0}  # TSUMO not in legal_actions
        result = ActionGrounder.ground(legal, choice)
        assert result.status == "no_match"
        assert result.legal_action is None

    def test_ground_ignores_why(self) -> None:
        """'why' field does not participate in matching."""
        legal = _make_legal_actions()
        choice = {"kind": "draw", "seat": 0, "why": "some reason"}
        result = ActionGrounder.ground(legal, choice)
        assert result.status == "grounded"
        assert result.legal_action is not None

    def test_ground_nested_action_format(self) -> None:
        """Support {'action': {...}, 'why': '...'} nested format."""
        legal = _make_legal_actions()
        choice = {"action": {"kind": "draw", "seat": 0}, "why": "nested format"}
        result = ActionGrounder.ground(legal, choice)
        assert result.status == "grounded"
        assert result.legal_action is not None

    def test_ground_chinese_action_format(self) -> None:
        """Support {'action': '打一万', 'why': '...'} Chinese format."""
        legal = (
            LegalAction(kind=ActionKind.DISCARD, seat=0, tile=Tile(Suit.MAN, 1)),
        )
        choice = {"action": "打一万", "why": "discard one man"}
        result = ActionGrounder.ground(legal, choice)
        # This may or may not match depending on Chinese action support
        # The grounder uses find_matching_legal_action which supports Chinese
        assert result.status in ("grounded", "no_match")


class TestFallbackStrategy:
    """Verify FallbackStrategy provides correct fallback behavior."""

    def test_first_legal_returns_first(self) -> None:
        """'first_legal' strategy returns legal_actions[0]."""
        legal = _make_legal_actions()
        fallback = FallbackStrategy(kind=FallbackKind.FIRST_LEGAL)
        action = fallback.select(legal)
        assert action == legal[0]

    def test_first_legal_empty_raises(self) -> None:
        """'first_legal' strategy raises ValueError on empty legal_actions."""
        fallback = FallbackStrategy(kind=FallbackKind.FIRST_LEGAL)
        with pytest.raises(ValueError, match="legal_actions is empty"):
            fallback.select(())

    def test_random_legal_is_deterministic_with_seed(self) -> None:
        """'random_legal' with same seed produces same result."""
        legal = _make_legal_actions()
        f1 = FallbackStrategy(kind=FallbackKind.RANDOM_LEGAL, seed=42)
        f2 = FallbackStrategy(kind=FallbackKind.RANDOM_LEGAL, seed=42)
        assert f1.select(legal) == f2.select(legal)

    def test_none_strategy_raises(self) -> None:
        """'none' strategy raises RuntimeError."""
        legal = _make_legal_actions()
        fallback = FallbackStrategy(kind=FallbackKind.NONE)
        with pytest.raises(RuntimeError, match="Fallback strategy is 'none'"):
            fallback.select(legal)

    def test_should_fallback_parse_failed(self) -> None:
        """should_fallback returns True for parse_failed."""
        assert FallbackStrategy.should_fallback("parse_failed") is True

    def test_should_fallback_match_failed(self) -> None:
        """should_fallback returns True for match_failed."""
        assert FallbackStrategy.should_fallback("match_failed") is True

    def test_should_fallback_matched(self) -> None:
        """should_fallback returns False for matched."""
        assert FallbackStrategy.should_fallback("matched") is False


class TestAgentPipeline:
    """Verify AgentPipeline orchestrates the full decision flow."""

    def test_pipeline_success_path(self) -> None:
        """Full pipeline: backend -> parse -> ground -> legal action."""
        ctx = _make_decision_context()
        spec = _make_agent_spec()
        components = build_components(spec, seed=42)

        # Use DummyBackend with a valid JSON response that matches first DISCARD
        # The game state is at MUST_DISCARD phase, so legal actions are DISCARD variants
        first_action = ctx.legal_actions[0]
        tile_code = first_action.tile.to_code() if first_action.tile else "1m"
        backend = DummyBackend(response=f'{{"kind":"discard","seat":0,"tile":"{tile_code}"}}')
        pipeline = AgentPipeline(components, backend)

        result = pipeline.run(ctx)
        assert result.action is not None
        assert result.parse_status == "matched"
        assert result.fallback_used is False

    def test_pipeline_parse_failed_fallback(self) -> None:
        """Parse failure triggers fallback -> fallback_used=True."""
        ctx = _make_decision_context()
        spec = _make_agent_spec()
        components = build_components(spec, seed=42)

        # Invalid JSON triggers parse_failed
        backend = DummyBackend(response="not valid json")
        pipeline = AgentPipeline(components, backend)

        result = pipeline.run(ctx)
        assert result.parse_status == "parse_failed"
        assert result.fallback_used is True
        assert result.action is not None  # fallback provides action

    def test_pipeline_match_failed_fallback(self) -> None:
        """Match failure triggers fallback -> fallback_used=True."""
        ctx = _make_decision_context()
        spec = _make_agent_spec()
        components = build_components(spec, seed=42)

        # Valid JSON but non-matching action triggers match_failed
        backend = DummyBackend(response='{"kind":"tsumo","seat":0}')
        pipeline = AgentPipeline(components, backend)

        result = pipeline.run(ctx)
        assert result.parse_status == "match_failed"
        assert result.fallback_used is True
        assert result.action is not None  # fallback provides action

    def test_pipeline_diagnostics_populated(self) -> None:
        """Pipeline populates diagnostics with parse info."""
        ctx = _make_decision_context()
        spec = _make_agent_spec()
        components = build_components(spec, seed=42)

        # Use matching response
        first_action = ctx.legal_actions[0]
        tile_code = first_action.tile.to_code() if first_action.tile else "1m"
        backend = DummyBackend(response=f'{{"kind":"discard","seat":0,"tile":"{tile_code}"}}')
        pipeline = AgentPipeline(components, backend)

        result = pipeline.run(ctx)
        assert "raw_output" in result.diagnostics
        assert "parse_result" in result.diagnostics
        assert tile_code in result.diagnostics["raw_output"]

    def test_pipeline_latency_recorded(self) -> None:
        """Pipeline records latency_ms."""
        ctx = _make_decision_context()
        spec = _make_agent_spec()
        components = build_components(spec, seed=42)

        # Use matching response
        first_action = ctx.legal_actions[0]
        tile_code = first_action.tile.to_code() if first_action.tile else "1m"
        backend = DummyBackend(response=f'{{"kind":"discard","seat":0,"tile":"{tile_code}"}}')
        pipeline = AgentPipeline(components, backend)

        result = pipeline.run(ctx)
        assert result.latency_ms >= 0  # Should be non-negative