"""全桌快照文本（``llm.table_snapshot_text``）。"""

from __future__ import annotations

from collections import Counter

from kernel import Action, ActionKind, apply, build_deck, initial_game_state, shuffle_deck
from kernel.event_log import HandOverEvent, WinSettlementLine
from kernel.replay_json import action_to_wire
from kernel.tiles.model import Suit, Tile
from llm.table_snapshot_text import (
    _concealed_sorted_with_turn_draw_note,
    action_wire_to_cn,
    format_hand_over_section,
    format_table_snapshot_block,
)


def test_format_snapshot_after_begin_round_contains_winds_and_header() -> None:
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=42))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    text = format_table_snapshot_block(
        state,
        hand_number=1,
        last_action_cn=action_wire_to_cn(
            action_to_wire(Action(ActionKind.BEGIN_ROUND, wall=w)),
            dealer_seat=state.table.dealer_seat,
        ),
    )
    assert "============= round 1 =============" in text
    assert "東風1局" in text or "東風" in text
    assert "东家" in text
    assert "南家" in text
    assert "点数：" in text
    assert "和了胜率：" in text
    assert "25000" in text
    assert "执行：" in text
    assert "-----------------------------------------------------" in text
    assert "（手牌）" not in text
    assert "（牌河）" not in text
    assert "（鸣牌）" not in text


def test_format_hand_over_section_shows_pattern_and_yaku() -> None:
    line = WinSettlementLine(
        seat=1,
        win_kind="ron",
        han=3,
        fu=30,
        hand_pattern="一般形",
        yakus=("立直", "表宝牌1"),
        discard_seat=0,
        payment_from_discarder=2900,
        tsumo_deltas=None,
        kyoutaku_share=0,
        points=2900,
    )
    ev = HandOverEvent(
        seat=None,
        sequence=0,
        winners=(1,),
        payments=(-2900, 2900, 0, 0),
        win_lines=(line,),
    )
    text = format_hand_over_section((ev,), dealer_seat=0)
    assert text is not None
    assert "本局和了：" in text
    assert "一般形" in text
    assert "荣和" in text
    assert "3番30符" in text
    assert "立直" in text
    assert "+2900点" in text


def test_action_wire_discard_uses_wind_label() -> None:
    w = action_wire_to_cn(
        {"kind": "discard", "seat": 1, "tile": "3m"},
        dealer_seat=0,
    )
    assert "南家" in w
    assert "3m" in w


def test_action_wire_discard_with_merged_draw_tile() -> None:
    w = action_wire_to_cn(
        {"kind": "discard", "seat": 2, "tile": "3s"},
        dealer_seat=0,
        draw_tile_code="9m",
    )
    assert "西家" in w
    assert "摸9m" in w
    assert "打牌" in w
    assert "3s" in w


def test_concealed_turn_draw_note_removes_one_copy_from_sorted_hand() -> None:
    """合并摸打快照：主串去掉一张摸牌，末位（牌码），避免 5mr…（5mr）重复。"""
    r5 = Tile(Suit.MAN, 5, is_red=True)
    tiles = [
        Tile(Suit.MAN, 4),
        r5,
        Tile(Suit.MAN, 6),
        Tile(Suit.MAN, 6),
        Tile(Suit.MAN, 7),
        Tile(Suit.MAN, 9),
        Tile(Suit.PIN, 4),
        Tile(Suit.PIN, 4),
        Tile(Suit.PIN, 5),
        Tile(Suit.HONOR, 2),
        Tile(Suit.HONOR, 2),
        Tile(Suit.HONOR, 3),
        Tile(Suit.HONOR, 3),
    ]
    s = _concealed_sorted_with_turn_draw_note(
        Counter(tiles), turn_draw_tile=r5, annotate=True
    )
    assert s == "4m6m6m7m9m4p4p5p2z2z3z3z（5mr）"
    body = s.split("（")[0]
    assert "5mr" not in body


def test_concealed_turn_draw_note_tsumogiri_hand_has_no_draw_tile() -> None:
    """摸切：手牌中已无切出张，主串 13 张不变，仅末位标摸牌。"""
    t3s = Tile(Suit.SOU, 3)
    tiles = [Tile(Suit.MAN, 1)] * 13  # 占位 13 张
    s = _concealed_sorted_with_turn_draw_note(
        Counter(tiles), turn_draw_tile=t3s, annotate=True
    )
    assert s.endswith("（3s）")
    assert s.count("1m") == 13
