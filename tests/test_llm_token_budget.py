"""LLM token 预算与公共事件流测试。"""

from __future__ import annotations

from kernel import Meld, MeldKind
from kernel.event_log import CallEvent, DiscardTileEvent, RoundBeginEvent
from llm.agent.event_journal import MatchJournal
from llm.agent.models.budget_config import PromptBudgetConfig
from llm.agent.models.diagnostics import PromptDiagnostics, summarize_prompt_diagnostics
from llm.agent.models.prompt_block import (
    BlockTokenUsage,
    PromptBlock,
    PromptBlockVariant,
)
from llm.agent.token_budget import PromptBudgetPlanner, TokenEstimateService
from llm.protocol import ChatMessage
from llm.wire import tile_from_code


def test_token_estimate_service_uses_deepseek_heuristic() -> None:
    estimator = TokenEstimateService()
    assert estimator.estimate_text("abcd") == 2
    assert estimator.estimate_text("中文") == 2
    assert estimator.estimate_text("abc中文") == 3


def test_prompt_budget_planner_compresses_lower_priority_block_first() -> None:
    estimator = TokenEstimateService(ascii_weight=1.0, cjk_weight=1.0, other_weight=1.0)
    planner = PromptBudgetPlanner(
        PromptBudgetConfig(
            max_context_tokens=19,
            max_output_tokens=3,
            context_compression_threshold=1.0,
        ),
        estimator=estimator,
    )
    blocks = [
        PromptBlock(
            block_id="system",
            role="system",
            priority=0,
            required=True,
            variants=(PromptBlockVariant("full", "SYS"),),
        ),
        PromptBlock(
            block_id="match_archive",
            role="user",
            priority=90,
            required=False,
            variants=(
                PromptBlockVariant("full", "AAAAAAAA"),
                PromptBlockVariant("snip", "AA"),
            ),
        ),
        PromptBlock(
            block_id="self_history",
            role="user",
            priority=60,
            required=False,
            variants=(
                PromptBlockVariant("full", "BBBBB"),
                PromptBlockVariant("snip", "BBB"),
            ),
        ),
        PromptBlock(
            block_id="current_turn",
            role="user",
            priority=0,
            required=True,
            variants=(PromptBlockVariant("full", "CCCCCC"),),
        ),
    ]

    plan = planner.plan(blocks)

    selected = {block.block_id: block for block in plan.blocks}
    assert plan.prompt_budget_tokens == 16
    assert plan.estimated_tokens == 16
    assert selected["match_archive"].state == "snip"
    assert selected["self_history"].state == "full"
    assert plan.diagnostics is not None
    assert plan.diagnostics.estimated_tokens == 16
    assert plan.diagnostics.prompt_budget_tokens == 16
    assert plan.diagnostics.max_context_tokens == 19
    assert plan.diagnostics.max_compression_state == "snip"
    assert plan.diagnostics.trimmed_blocks == ()
    assert plan.diagnostics.over_budget is False
    assert PromptDiagnostics.from_wire(plan.diagnostics.to_wire()) == plan.diagnostics


def test_prompt_budget_planner_records_dropped_optional_blocks() -> None:
    estimator = TokenEstimateService(ascii_weight=1.0, cjk_weight=1.0, other_weight=1.0)
    planner = PromptBudgetPlanner(
        PromptBudgetConfig(
            max_context_tokens=10,
            max_output_tokens=1,
            context_compression_threshold=1.0,
        ),
        estimator=estimator,
    )

    plan = planner.plan(
        [
            PromptBlock(
                block_id="required",
                role="system",
                priority=0,
                required=True,
                variants=(PromptBlockVariant("full", "RRRRRRRR"),),
            ),
            PromptBlock(
                block_id="optional",
                role="user",
                priority=80,
                required=False,
                variants=(
                    PromptBlockVariant("full", "OOOOOOOO"),
                    PromptBlockVariant("collapse", "OOOOOO"),
                ),
            ),
        ]
    )

    assert plan.estimated_tokens == 8
    assert plan.trimmed_blocks == ("optional",)
    assert plan.diagnostics is not None
    assert plan.diagnostics.max_compression_state == "drop"
    assert plan.diagnostics.trimmed_blocks == ("optional",)
    assert [block.block_id for block in plan.diagnostics.selected_blocks] == ["required"]


def test_prompt_diagnostics_summary_aggregates_token_pressure() -> None:
    selected = (
        BlockTokenUsage(
            block_id="system",
            role="system",
            priority=0,
            required=True,
            state="full",
            estimated_tokens=100,
        ),
    )
    first = PromptDiagnostics(
        estimated_tokens=100,
        prompt_budget_tokens=200,
        max_context_tokens=300,
        max_output_tokens=50,
        context_compression_threshold=1.0,
        selected_blocks=selected,
        trimmed_blocks=(),
        max_compression_state="full",
        over_budget=False,
    )
    second = PromptDiagnostics(
        estimated_tokens=220,
        prompt_budget_tokens=200,
        max_context_tokens=300,
        max_output_tokens=50,
        context_compression_threshold=1.0,
        selected_blocks=selected,
        trimmed_blocks=("public_history",),
        max_compression_state="drop",
        over_budget=True,
    )

    summary = summarize_prompt_diagnostics((first, None, second))

    assert summary.request_count == 2
    assert summary.latest == second
    assert summary.peak == second
    assert summary.average_estimated_tokens == 160
    assert summary.over_budget_count == 1
    assert summary.compression_state_counts == (("full", 1), ("drop", 1))
    assert summary.trimmed_block_counts == (("public_history", 1),)


def test_match_journal_projects_public_history_and_archive() -> None:
    journal = MatchJournal()
    journal.start_hand(
        1,
        (
            RoundBeginEvent(
                seat=None,
                sequence=0,
                dealer_seat=0,
                dora_indicator=tile_from_code("1m"),
                seeds=(0, 1, 2, 3),
            ),
        ),
    )
    journal.append_events(
        (
            DiscardTileEvent(
                seat=1,
                sequence=1,
                tile=tile_from_code("5p"),
                is_tsumogiri=False,
                declare_riichi=True,
            ),
            CallEvent(
                seat=2,
                sequence=2,
                meld=Meld(
                    kind=MeldKind.PON,
                    tiles=(
                        tile_from_code("3s"),
                        tile_from_code("3s"),
                        tile_from_code("3s"),
                    ),
                    called_tile=tile_from_code("3s"),
                    from_seat=1,
                ),
                call_kind="pon",
            ),
        ),
    )

    projected = journal.project_current_hand(
        viewer_seat=1,
        detailed=True,
        history_budget=8,
        compression_level="autocompact",
    )

    assert "第1局开始" in projected
    assert "我打5p立直" in projected
    assert "当前主要威胁: 家1" in projected

    journal.archive_current_hand()
    archived = journal.project_archived_hands(
        archive_budget=4,
        compression_level="autocompact",
    )

    assert "本场已完成 1 局" in archived
    assert "第1局开始" in archived


# --- TokenEstimateService CJK/Unicode 范围测试 ---

class TestTokenEstimateServiceCJKRanges:
    """测试 TokenEstimateService 对各种 CJK/Unicode 范围的识别。"""

    def test_cjk_extension_a(self) -> None:
        """CJK Extension A (U+3400-U+4DBF) 应被识别为 CJK-like。"""
        estimator = TokenEstimateService()
        # 㐀 = U+3400, 䶮 = U+4DAF
        result = estimator.estimate_text("㐀䶮")
        assert result > 0  # 每个 CJK Extension A 字符估算为 2 token

    def test_japanese_hiragana(self) -> None:
        """日文平假名 (U+3040-U+30FF) 应被识别为 CJK-like。"""
        estimator = TokenEstimateService()
        result = estimator.estimate_text("あいうえお")
        assert result > 0

    def test_japanese_katakana(self) -> None:
        """日文片假名也应被识别为 CJK-like。"""
        estimator = TokenEstimateService()
        result = estimator.estimate_text("アイウエオ")
        assert result > 0

    def test_korean_syllables(self) -> None:
        """韩文音节 (U+AC00-U+D7AF) 应被识别为 CJK-like。"""
        estimator = TokenEstimateService()
        # 한글 = 韩文
        result = estimator.estimate_text("한글")
        assert result > 0


class TestTokenEstimateServiceEdgeCases:
    """测试 TokenEstimateService 边缘场景。"""

    def test_empty_string_returns_zero(self) -> None:
        """空字符串应返回 0 token。"""
        estimator = TokenEstimateService()
        assert estimator.estimate_text("") == 0

    def test_estimate_messages_empty_list(self) -> None:
        """空消息列表应返回 0 token。"""
        estimator = TokenEstimateService()
        assert estimator.estimate_messages([]) == 0

    def test_estimate_messages_single(self) -> None:
        """单条消息应正确估算。"""
        estimator = TokenEstimateService()
        messages = [ChatMessage(role="user", content="hello")]
        result = estimator.estimate_messages(messages)
        assert result == estimator.estimate_text("hello")

    def test_estimate_messages_multiple(self) -> None:
        """多条消息应正确汇总估算。"""
        estimator = TokenEstimateService()
        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="你好"),
            ChatMessage(role="assistant", content="Hello!"),
        ]
        result = estimator.estimate_messages(messages)
        expected = (
            estimator.estimate_text("You are helpful.")
            + estimator.estimate_text("你好")
            + estimator.estimate_text("Hello!")
        )
        assert result == expected
