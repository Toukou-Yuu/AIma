"""测试 prompts/sections.py。

测试 section 实现。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from prompts.sections import (
    SECTION_RENDERERS,
    estimate_tokens,
    get_renderer,
    render_dora,
    render_game_state,
    render_hand,
    render_legal_actions,
    render_memory,
    render_output_format,
    render_riichi_state,
    render_river,
    render_system_prompt,
)
from prompts.schema import PromptSectionSpec


# ---------------------------------------------------------------------------
# Mock 对象
# ---------------------------------------------------------------------------


@dataclass
class MockTile:
    """Mock Tile."""

    suit: Any = None
    rank: int = 1

    def __str__(self) -> str:
        return f"{self.rank}m"

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))


@dataclass
class MockSuit:
    """Mock Suit."""

    value: str = "m"

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass
class MockMeld:
    """Mock Meld."""

    kind: Any = None
    tiles: tuple[MockTile, ...] = ()

    @dataclass
    class Kind:
        value: str = "chi"


@dataclass
class MockRiverEntry:
    """Mock RiverEntry."""

    tile: MockTile = field(default_factory=MockTile)
    seat: int = 0
    is_riichi: bool = False
    is_tsumogiri: bool = False


@dataclass
class MockGameState:
    """Mock GameState."""

    phase: Any = None
    board: Any = None
    table: Any = None


@dataclass
class MockTable:
    """Mock Table."""

    dealer_seat: int = 0
    scores: tuple[int, ...] = (25000, 25000, 25000, 25000)
    honba: int = 0
    kyoutaku: int = 0


@dataclass
class MockObservation:
    """Mock Observation."""

    hand: Counter[MockTile] | None = None
    melds: tuple[MockMeld, ...] = ()
    river: tuple[MockRiverEntry, ...] = ()
    dora_indicators: tuple[MockTile, ...] = ()
    ura_indicators: tuple[MockTile, ...] | None = None
    riichi_state: tuple[bool, ...] = (False, False, False, False)
    scores: tuple[int, ...] = (25000, 25000, 25000, 25000)
    honba: int = 0
    kyoutaku: int = 0


@dataclass
class MockLegalAction:
    """Mock LegalAction."""

    kind: Any = None
    tile: MockTile | None = None
    meld: MockMeld | None = None

    @dataclass
    class Kind:
        value: str = "DISCARD"


@dataclass
class MockDecisionContext:
    """Mock DecisionContext 用于测试。"""

    match_id: str = "test_match"
    job_id: str = "test_job"
    hand_index: int = 1
    step_index: int = 10
    seed: int = 42
    seat: int = 0
    phase: str = "in_round"
    state: MockGameState = field(default_factory=MockGameState)
    observation: MockObservation = field(default_factory=MockObservation)
    legal_actions: tuple[MockLegalAction, ...] = ()

    def __post_init__(self) -> None:
        self.state.table = MockTable()


# ---------------------------------------------------------------------------
# estimate_tokens 测试
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    """estimate_tokens 测试。"""

    def test_empty_text_returns_zero(self) -> None:
        """空文本返回 0。"""
        assert estimate_tokens("") == 0

    def test_estimates_from_length(self) -> None:
        """从长度估算。"""
        # estimate_tokens 使用 len(text) // 4 + 1
        text = "aaaa"  # 4 字符: 4 // 4 + 1 = 2
        assert estimate_tokens(text) == 2

        text = "aaaaaaaa"  # 8 字符: 8 // 4 + 1 = 3
        assert estimate_tokens(text) == 3

    def test_estimates_longer_text(self) -> None:
        """估算较长文本。"""
        text = "This is a longer text with many words"
        result = estimate_tokens(text)
        # 约 len(text) / 4 + 1
        expected = len(text) // 4 + 1
        assert result == expected


# ---------------------------------------------------------------------------
# get_renderer 测试
# ---------------------------------------------------------------------------


class TestGetRenderer:
    """get_renderer 测试。"""

    def test_gets_existing_renderer(self) -> None:
        """获取存在的 renderer。"""
        renderer = get_renderer("system_prompt")
        assert renderer is render_system_prompt

        renderer = get_renderer("game_state")
        assert renderer is render_game_state

    def test_returns_none_for_unknown_renderer(self) -> None:
        """未知 renderer 返回 None。"""
        renderer = get_renderer("nonexistent_renderer")
        assert renderer is None

    def test_section_renderers_registry(self) -> None:
        """SECTION_RENDERERS 注册表。"""
        assert "system_prompt" in SECTION_RENDERERS
        assert "game_state" in SECTION_RENDERERS
        assert "hand" in SECTION_RENDERERS
        assert "river" in SECTION_RENDERERS
        assert "dora" in SECTION_RENDERERS
        assert "riichi_state" in SECTION_RENDERERS
        assert "legal_actions" in SECTION_RENDERERS
        assert "memory" in SECTION_RENDERERS
        assert "output_format" in SECTION_RENDERERS


# ---------------------------------------------------------------------------
# render_system_prompt 测试
# ---------------------------------------------------------------------------


class TestRenderSystemPrompt:
    """render_system_prompt 测试。"""

    def test_default_variant(self) -> None:
        """默认 variant。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="system_prompt", variant=None)

        result = render_system_prompt(ctx, spec)
        assert "You are a Mahjong player" in result

    def test_riichi_variant(self) -> None:
        """riichi variant。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="system_prompt", variant="riichi")

        result = render_system_prompt(ctx, spec)
        assert "Japanese Riichi Mahjong" in result
        assert "JSON object" in result

    def test_uses_options_role(self) -> None:
        """使用 options.role。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(
            id="system_prompt",
            variant="default",
            options={"role": "Expert AI player"},
        )

        result = render_system_prompt(ctx, spec)
        assert "Expert AI player" in result

    def test_unknown_variant_falls_back(self) -> None:
        """未知 variant 回退到默认。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="system_prompt", variant="unknown")

        result = render_system_prompt(ctx, spec)
        assert "You are a Mahjong player" in result


# ---------------------------------------------------------------------------
# render_game_state 测试
# ---------------------------------------------------------------------------


class TestRenderGameState:
    """render_game_state 测试。"""

    def test_render_basic_state(self) -> None:
        """渲染基本状态。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="game_state")

        result = render_game_state(ctx, spec)
        assert "## Game State" in result
        assert "Phase:" in result
        assert "Your seat:" in result
        assert "Dealer seat:" in result
        assert "Hand index:" in result
        assert "Step index:" in result

    def test_render_scores(self) -> None:
        """渲染分数。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="game_state")

        result = render_game_state(ctx, spec)
        assert "Scores:" in result
        assert "Seat 0" in result
        assert "25000" in result

    def test_render_honba_kyoutaku(self) -> None:
        """渲染本场供托。"""
        ctx = MockDecisionContext()
        ctx.state.table = MockTable(honba=2, kyoutaku=3)
        spec = PromptSectionSpec(id="game_state")

        result = render_game_state(ctx, spec)
        assert "Honba: 2" in result
        assert "Kyoutaku" in result and "3" in result


# ---------------------------------------------------------------------------
# render_hand 测试
# ---------------------------------------------------------------------------


class TestRenderHand:
    """render_hand 测试。"""

    def test_render_empty_hand(self) -> None:
        """渲染空手牌。"""
        ctx = MockDecisionContext()
        ctx.observation.hand = Counter()
        spec = PromptSectionSpec(id="hand")

        result = render_hand(ctx, spec)
        assert "## Your Hand" in result
        assert "(empty)" in result

    def test_render_null_hand(self) -> None:
        """渲染 null 手牌。"""
        ctx = MockDecisionContext()
        ctx.observation.hand = None
        spec = PromptSectionSpec(id="hand")

        result = render_hand(ctx, spec)
        assert "(no tiles)" in result

    def test_render_with_melds(self) -> None:
        """渲染带副露。"""
        ctx = MockDecisionContext()
        mock_suit = MockSuit(value="m")
        ctx.observation.hand = Counter([MockTile(suit=mock_suit)])
        ctx.observation.melds = (
            MockMeld(kind=MockMeld.Kind(value="chi"), tiles=(MockTile(suit=mock_suit), MockTile(suit=mock_suit), MockTile(suit=mock_suit))),
        )
        spec = PromptSectionSpec(id="hand")

        result = render_hand(ctx, spec)
        assert "Melds:" in result or "melds" in result.lower()


# ---------------------------------------------------------------------------
# render_river 测试
# ---------------------------------------------------------------------------


class TestRenderRiver:
    """render_river 测试。"""

    def test_render_empty_river(self) -> None:
        """渲染空河。"""
        ctx = MockDecisionContext()
        ctx.observation.river = ()
        spec = PromptSectionSpec(id="river")

        result = render_river(ctx, spec)
        assert "## River" in result
        assert "(empty)" in result

    def test_render_with_entries(self) -> None:
        """渲染带条目。"""
        ctx = MockDecisionContext()
        tile1 = MockTile(rank=1)
        tile2 = MockTile(rank=2)
        ctx.observation.river = (
            MockRiverEntry(tile=tile1, seat=0, is_riichi=False, is_tsumogiri=False),
            MockRiverEntry(tile=tile2, seat=1, is_riichi=True, is_tsumogiri=True),
        )
        spec = PromptSectionSpec(id="river")

        result = render_river(ctx, spec)
        assert "## River" in result
        assert "Seat 0" in result
        assert "Seat 1" in result
        assert "*" in result  # riichi marker
        assert "'" in result  # tsumogiri marker

    def test_max_items_limit(self) -> None:
        """max_items 限制。"""
        ctx = MockDecisionContext()
        # 创建 10 个条目
        entries = tuple(
            MockRiverEntry(tile=MockTile(rank=i), seat=0)
            for i in range(10)
        )
        ctx.observation.river = entries
        spec = PromptSectionSpec(id="river", max_items=5)

        result = render_river(ctx, spec)
        # 只显示最后 5 个
        lines = result.split("\n")
        seat_line = [l for l in lines if "Seat 0" in l][0]
        # 应只有 5 个牌
        tiles = seat_line.split(": ")[1].split()
        assert len(tiles) == 5


# ---------------------------------------------------------------------------
# render_dora 测试
# ---------------------------------------------------------------------------


class TestRenderDora:
    """render_dora 测试。"""

    def test_render_no_dora(self) -> None:
        """渲染无宝牌。"""
        ctx = MockDecisionContext()
        ctx.observation.dora_indicators = ()
        spec = PromptSectionSpec(id="dora")

        result = render_dora(ctx, spec)
        assert "## Dora Indicators" in result
        assert "(none revealed)" in result

    def test_render_with_dora(self) -> None:
        """渲染带宝牌。"""
        ctx = MockDecisionContext()
        ctx.observation.dora_indicators = (MockTile(rank=1), MockTile(rank=2))
        spec = PromptSectionSpec(id="dora")

        result = render_dora(ctx, spec)
        assert "## Dora Indicators" in result
        assert "1m" in result
        assert "2m" in result

    def test_render_with_ura(self) -> None:
        """渲染带里宝。"""
        ctx = MockDecisionContext()
        ctx.observation.dora_indicators = (MockTile(rank=1),)
        ctx.observation.ura_indicators = (MockTile(rank=5),)
        spec = PromptSectionSpec(id="dora")

        result = render_dora(ctx, spec)
        assert "Ura-dora" in result
        assert "5m" in result


# ---------------------------------------------------------------------------
# render_riichi_state 测试
# ---------------------------------------------------------------------------


class TestRenderRiichiState:
    """render_riichi_state 测试。"""

    def test_render_no_riichi(self) -> None:
        """渲染无立直。"""
        ctx = MockDecisionContext()
        ctx.observation.riichi_state = (False, False, False, False)
        spec = PromptSectionSpec(id="riichi_state")

        result = render_riichi_state(ctx, spec)
        assert "## Riichi State" in result
        assert "not riichi" in result

    def test_render_with_riichi(self) -> None:
        """渲染带立直。"""
        ctx = MockDecisionContext()
        ctx.observation.riichi_state = (True, False, True, False)
        spec = PromptSectionSpec(id="riichi_state")

        result = render_riichi_state(ctx, spec)
        assert "Seat 0: RIICHI" in result
        assert "Seat 1: not riichi" in result
        assert "Seat 2: RIICHI" in result


# ---------------------------------------------------------------------------
# render_legal_actions 测试
# ---------------------------------------------------------------------------


class TestRenderLegalActions:
    """render_legal_actions 测试。"""

    def test_render_no_actions(self) -> None:
        """渲染无动作。"""
        ctx = MockDecisionContext()
        ctx.legal_actions = ()
        spec = PromptSectionSpec(id="legal_actions")

        result = render_legal_actions(ctx, spec)
        assert "## Legal Actions" in result
        assert "Total: 0" in result

    def test_render_with_actions(self) -> None:
        """渲染带动作。"""
        ctx = MockDecisionContext()
        action1 = MockLegalAction(
            kind=MockLegalAction.Kind(value="DISCARD"),
            tile=MockTile(rank=1),
        )
        action2 = MockLegalAction(
            kind=MockLegalAction.Kind(value="DRAW"),
        )
        ctx.legal_actions = (action1, action2)
        spec = PromptSectionSpec(id="legal_actions")

        result = render_legal_actions(ctx, spec)
        assert "## Legal Actions" in result
        assert "Total: 2" in result
        assert "DISCARD" in result
        assert "DRAW" in result

    def test_max_items_limit(self) -> None:
        """max_items 限制。"""
        ctx = MockDecisionContext()
        # 创建 10 个动作
        actions = tuple(
            MockLegalAction(kind=MockLegalAction.Kind(value="DISCARD"), tile=MockTile(rank=i))
            for i in range(10)
        )
        ctx.legal_actions = actions
        spec = PromptSectionSpec(id="legal_actions", max_items=5)

        result = render_legal_actions(ctx, spec)
        assert "Total: 10" in result
        assert "... and 5 more" in result

    def test_render_with_meld_action(self) -> None:
        """渲染带副露动作。"""
        ctx = MockDecisionContext()
        meld = MockMeld(kind=MockMeld.Kind(value="chi"), tiles=(MockTile(), MockTile(), MockTile()))
        action = MockLegalAction(
            kind=MockLegalAction.Kind(value="OPEN_MELD"),
            meld=meld,
        )
        ctx.legal_actions = (action,)
        spec = PromptSectionSpec(id="legal_actions")

        result = render_legal_actions(ctx, spec)
        assert "OPEN_MELD" in result
        assert "[" in result


# ---------------------------------------------------------------------------
# render_memory 测试
# ---------------------------------------------------------------------------


class TestRenderMemory:
    """render_memory 测试。"""

    def test_render_no_source(self) -> None:
        """渲染无 source。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="memory", source=None)

        result = render_memory(ctx, spec)
        assert result == ""

    def test_render_with_empty_content(self) -> None:
        """渲染空内容。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(
            id="memory",
            source="memory_db",
            options={},
        )

        result = render_memory(ctx, spec)
        assert result == ""

    def test_render_with_content(self) -> None:
        """渲染带内容。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(
            id="memory",
            source="memory_db",
            options={"content": "Previous game memory"},
        )

        result = render_memory(ctx, spec)
        assert "## Memory" in result
        assert "Previous game memory" in result


# ---------------------------------------------------------------------------
# render_output_format 测试
# ---------------------------------------------------------------------------


class TestRenderOutputFormat:
    """render_output_format 测试。"""

    def test_json_action_variant(self) -> None:
        """json_action variant。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="output_format", variant="json_action")

        result = render_output_format(ctx, spec)
        assert "## Output Format" in result
        assert "JSON object" in result
        assert '"action"' in result
        assert '"why"' in result

    def test_natural_action_variant(self) -> None:
        """natural_action variant。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="output_format", variant="natural_action")

        result = render_output_format(ctx, spec)
        assert "## Output Format" in result
        assert "natural language" in result

    def test_default_variant(self) -> None:
        """默认 variant。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="output_format", variant=None)

        result = render_output_format(ctx, spec)
        assert "JSON object" in result

    def test_unknown_variant_falls_back(self) -> None:
        """未知 variant 回退。"""
        ctx = MockDecisionContext()
        spec = PromptSectionSpec(id="output_format", variant="unknown")

        result = render_output_format(ctx, spec)
        assert "JSON object" in result


# ---------------------------------------------------------------------------
# 格式化测试
# ---------------------------------------------------------------------------


class TestActionFormatting:
    """动作格式化测试。"""

    def test_discard_with_tile(self) -> None:
        """DISCARD 带牌。"""
        from prompts.sections import _format_action

        action = MockLegalAction(
            kind=MockLegalAction.Kind(value="DISCARD"),
            tile=MockTile(rank=5),
        )
        result = _format_action(action)
        assert result == "DISCARD 5m"

    def test_action_without_tile(self) -> None:
        """动作无牌。"""
        from prompts.sections import _format_action

        action = MockLegalAction(kind=MockLegalAction.Kind(value="DRAW"))
        result = _format_action(action)
        assert result == "DRAW"

    def test_meld_action(self) -> None:
        """副露动作。"""
        from prompts.sections import _format_action

        tiles = (MockTile(rank=1), MockTile(rank=2), MockTile(rank=3))
        meld = MockMeld(kind=MockMeld.Kind(value="chi"), tiles=tiles)
        action = MockLegalAction(
            kind=MockLegalAction.Kind(value="OPEN_MELD"),
            meld=meld,
        )
        result = _format_action(action)
        assert "OPEN_MELD" in result
        assert "[" in result
        assert "]" in result