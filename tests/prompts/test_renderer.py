"""测试 prompts/renderer.py。

测试渲染逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from models.backend import ChatMessage
from prompts.renderer import PromptRenderer, PromptRenderResult, SectionRenderResult
from prompts.schema import PromptBudgetSpec, PromptSectionSpec, PromptSpec


# ---------------------------------------------------------------------------
# Mock 对象
# ---------------------------------------------------------------------------


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

    hand: Any = None
    melds: tuple[Any, ...] = ()
    river: tuple[Any, ...] = ()
    dora_indicators: tuple[Any, ...] = ()
    ura_indicators: tuple[Any, ...] | None = None
    riichi_state: tuple[bool, ...] = (False, False, False, False)
    scores: tuple[int, ...] = (25000, 25000, 25000, 25000)
    honba: int = 0
    kyoutaku: int = 0


@dataclass
class MockLegalAction:
    """Mock LegalAction."""

    kind: Any = None
    tile: Any = None
    meld: Any = None

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
# 测试
# ---------------------------------------------------------------------------


class TestSectionRenderResult:
    """SectionRenderResult 测试。"""

    def test_creates_result(self) -> None:
        """创建结果。"""
        result = SectionRenderResult(
            id="section1",
            content="content",
            enabled=True,
            token_estimate=100,
            skipped=False,
        )

        assert result.id == "section1"
        assert result.content == "content"
        assert result.enabled is True
        assert result.token_estimate == 100
        assert result.skipped is False
        assert result.skip_reason is None

    def test_skipped_result(self) -> None:
        """跳过的结果。"""
        result = SectionRenderResult(
            id="section1",
            content="",
            enabled=False,
            token_estimate=0,
            skipped=True,
            skip_reason="disabled",
        )

        assert result.skipped is True
        assert result.skip_reason == "disabled"


class TestPromptRenderResult:
    """PromptRenderResult 测试。"""

    def test_creates_result(self) -> None:
        """创建结果。"""
        messages = (
            ChatMessage(role="system", content="system content"),
            ChatMessage(role="user", content="user content"),
        )
        sections = [
            SectionRenderResult(id="s1", content="c1", enabled=True, token_estimate=10, skipped=False),
        ]

        result = PromptRenderResult(
            messages=messages,
            sections=sections,
            total_tokens=10,
        )

        assert result.messages == messages
        assert result.sections == sections
        assert result.total_tokens == 10

    def test_default_values(self) -> None:
        """默认值。"""
        result = PromptRenderResult(messages=())

        assert result.messages == ()
        assert result.sections == []
        assert result.total_tokens == 0


class TestPromptRenderer:
    """PromptRenderer 测试。"""

    def test_init_with_spec(self) -> None:
        """使用 spec 初始化。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[],
        )
        renderer = PromptRenderer(spec)

        assert renderer.spec == spec
        assert renderer._section_cache == {}

    def test_render_disabled_section(self) -> None:
        """渲染禁用 section。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="disabled_section", enabled=False),
            ],
        )
        renderer = PromptRenderer(spec)

        ctx = MockDecisionContext()
        result = renderer.render(ctx)

        assert len(result.sections) == 1
        assert result.sections[0].skipped is True
        assert result.sections[0].skip_reason == "disabled"
        assert result.messages == ()

    def test_render_unknown_renderer(self) -> None:
        """渲染未知 renderer。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="unknown", enabled=True, renderer="nonexistent"),
            ],
        )
        renderer = PromptRenderer(spec)

        ctx = MockDecisionContext()
        result = renderer.render(ctx)

        assert len(result.sections) == 1
        assert result.sections[0].skipped is True
        assert "unknown renderer" in result.sections[0].skip_reason

    def test_get_section_role_system(self) -> None:
        """system section role。"""
        assert PromptRenderer._get_section_role("system_prompt") == "system"
        assert PromptRenderer._get_section_role("system_rules") == "system"

    def test_get_section_role_user(self) -> None:
        """user section role。"""
        assert PromptRenderer._get_section_role("game_state") == "user"
        assert PromptRenderer._get_section_role("hand") == "user"

    def test_render_messages_convenience(self) -> None:
        """render_messages 便捷方法。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[],
        )
        renderer = PromptRenderer(spec)

        ctx = MockDecisionContext()
        messages = renderer.render_messages(ctx)

        assert messages == ()

    def test_render_with_mock_renderer(self) -> None:
        """使用 mock renderer 渲染。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="test_section", enabled=True, renderer="test_renderer"),
            ],
        )
        renderer = PromptRenderer(spec)

        # Mock get_renderer
        def mock_renderer(ctx: Any, spec: Any) -> str:
            return "rendered content"

        with patch("prompts.renderer.get_renderer", return_value=mock_renderer):
            ctx = MockDecisionContext()
            result = renderer.render(ctx)

        assert len(result.sections) == 1
        assert result.sections[0].content == "rendered content"
        assert result.sections[0].skipped is False

    def test_render_exception_handling(self) -> None:
        """渲染异常处理。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="error_section", enabled=True, renderer="error_renderer"),
            ],
        )
        renderer = PromptRenderer(spec)

        # Mock get_renderer 返回抛异常的函数
        def error_renderer(ctx: Any, spec: Any) -> str:
            raise RuntimeError("render error")

        with patch("prompts.renderer.get_renderer", return_value=error_renderer):
            ctx = MockDecisionContext()
            result = renderer.render(ctx)

        assert len(result.sections) == 1
        assert result.sections[0].skipped is True
        assert result.sections[0].skip_reason == "render error"

    def test_max_tokens_truncation(self) -> None:
        """max_tokens 截断。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="long_section", enabled=True, max_tokens=10),
            ],
        )
        renderer = PromptRenderer(spec)

        # Mock 返回长内容
        long_content = "a" * 100  # 100 字符，约 25 tokens

        with patch("prompts.renderer.get_renderer", return_value=lambda c, s: long_content):
            ctx = MockDecisionContext()
            result = renderer.render(ctx)

        # 应被截断到约 40 字符 (10 tokens * 4)
        assert len(result.sections[0].content) <= 40


class TestPromptRendererIntegration:
    """PromptRenderer 集成测试。"""

    def test_builds_system_and_user_messages(self) -> None:
        """构建 system 和 user 消息。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="system_prompt", enabled=True),
                PromptSectionSpec(id="game_state", enabled=True),
            ],
        )
        renderer = PromptRenderer(spec)

        # Mock renderers
        def system_renderer(ctx: Any, s: Any) -> str:
            return "System prompt content"

        def game_renderer(ctx: Any, s: Any) -> str:
            return "Game state content"

        renderers = {
            "system_prompt": system_renderer,
            "game_state": game_renderer,
        }

        with patch("prompts.renderer.get_renderer", side_effect=lambda n: renderers.get(n)):
            ctx = MockDecisionContext()
            result = renderer.render(ctx)

        assert len(result.messages) == 2
        assert result.messages[0].role == "system"
        assert result.messages[1].role == "user"

    def test_empty_content_skipped(self) -> None:
        """空内容被跳过。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="empty_section", enabled=True),
            ],
        )
        renderer = PromptRenderer(spec)

        with patch("prompts.renderer.get_renderer", return_value=lambda c, s: ""):
            ctx = MockDecisionContext()
            result = renderer.render(ctx)

        assert result.sections[0].skipped is True
        assert result.sections[0].skip_reason == "empty content"
        assert result.messages == ()

    def test_token_estimation(self) -> None:
        """token 估算。"""
        spec = PromptSpec(
            template_id="test",
            version="1.0",
            sections=[
                PromptSectionSpec(id="s1", enabled=True),
                PromptSectionSpec(id="s2", enabled=True),
            ],
        )
        renderer = PromptRenderer(spec)

        content1 = "short content"  # 约 3 tokens
        content2 = "longer content here"  # 约 5 tokens

        renderers = {
            "s1": lambda c, s: content1,
            "s2": lambda c, s: content2,
        }

        with patch("prompts.renderer.get_renderer", side_effect=lambda n: renderers.get(n)):
            ctx = MockDecisionContext()
            result = renderer.render(ctx)

        # 总 token 应为两段内容之和
        assert result.total_tokens > 0


class TestSectionRoleConvention:
    """Section role 约定测试。"""

    def test_all_system_prefixes(self) -> None:
        """所有 system_ 前缀返回 system role。"""
        for prefix in ["system_prompt", "system_rules", "system_context", "system_game"]:
            assert PromptRenderer._get_section_role(prefix) == "system"

    def test_non_system_prefixes(self) -> None:
        """非 system_ 前缀返回 user role。"""
        for prefix in ["game_state", "hand", "river", "dora", "legal_actions"]:
            assert PromptRenderer._get_section_role(prefix) == "user"