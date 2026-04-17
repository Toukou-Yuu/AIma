"""LLM token 预算与公共事件流测试。"""

from __future__ import annotations

from kernel import Meld, MeldKind
from kernel.event_log import CallEvent, DiscardTileEvent, RoundBeginEvent
from llm.agent.event_journal import MatchJournal
from llm.agent.token_budget import (
    PromptBlock,
    PromptBlockVariant,
    PromptBudgetConfig,
    PromptBudgetPlanner,
    TokenEstimateService,
)
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
            context_budget_tokens=21,
            reserved_output_tokens=3,
            safety_margin_tokens=2,
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
