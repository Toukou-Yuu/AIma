"""simple_log 纯函数覆盖。"""

from __future__ import annotations

import io

from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    FlowEvent,
    HandOverEvent,
    MatchEndEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
    WinSettlementLine,
)
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from llm.simple_log import (
    _家,
    append_simple_log_block,
    format_action_wire_supplement,
    format_game_event,
)


# ── _家 ──────────────────────────────────────────────────────────────────────

def test_家_with_seat() -> None:
    assert _家(0) == "家0"
    assert _家(3) == "家3"


def test_家_none() -> None:
    assert _家(None) == "（未知席）"


# ── format_game_event ────────────────────────────────────────────────────────

def test_format_round_begin() -> None:
    ev = RoundBeginEvent(seat=None, sequence=0, dealer_seat=2, dora_indicator=Tile(Suit.MAN, 1), seeds=(0, 1, 2, 3))
    out = format_game_event(ev)
    assert "亲=家2" in out
    assert "1m" in out


def test_format_draw_tile() -> None:
    ev = DrawTileEvent(seat=1, sequence=1, tile=Tile(Suit.PIN, 5), is_rinshan=False, wall_remaining=60)
    out = format_game_event(ev)
    assert "家1" in out
    assert "本墙" in out
    assert "5p" in out
    assert "60" in out


def test_format_draw_tile_rinshan() -> None:
    ev = DrawTileEvent(seat=0, sequence=2, tile=Tile(Suit.SOU, 3), is_rinshan=True, wall_remaining=10)
    out = format_game_event(ev)
    assert "岭上" in out


def test_format_discard_tsumogiri_no_riichi() -> None:
    ev = DiscardTileEvent(seat=0, sequence=3, tile=Tile(Suit.MAN, 9), is_tsumogiri=True, declare_riichi=False)
    out = format_game_event(ev)
    assert "摸切" in out
    assert "立直" not in out


def test_format_discard_with_riichi() -> None:
    ev = DiscardTileEvent(seat=2, sequence=4, tile=Tile(Suit.PIN, 1), is_tsumogiri=False, declare_riichi=True)
    out = format_game_event(ev)
    assert "手切" in out
    assert "立直宣言" in out


def test_format_call_chi() -> None:
    meld = Meld(
        kind=MeldKind.CHI,
        tiles=(Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3)),
        called_tile=Tile(Suit.MAN, 3),
        from_seat=0,
    )
    ev = CallEvent(seat=1, sequence=5, meld=meld, call_kind="chi")
    out = format_game_event(ev)
    assert "吃" in out
    assert "鸣入" in out


def test_format_call_unknown_kind() -> None:
    """call_kind 不在 _CALL_CN 时回退到原 kind 值."""
    meld = Meld(
        kind=MeldKind.ANKAN,
        tiles=(Tile(Suit.SOU, 4), Tile(Suit.SOU, 4), Tile(Suit.SOU, 4), Tile(Suit.SOU, 4)),
    )
    ev = CallEvent(seat=0, sequence=6, meld=meld, call_kind="unknown_kind")
    out = format_game_event(ev)
    assert "unknown_kind" in out


def test_format_ron() -> None:
    ev = RonEvent(seat=3, sequence=7, win_tile=Tile(Suit.MAN, 5), discard_seat=1)
    out = format_game_event(ev)
    assert "荣和" in out
    assert "家3" in out
    assert "家1" in out


def test_format_tsumo() -> None:
    ev = TsumoEvent(seat=0, sequence=8, win_tile=Tile(Suit.PIN, 7), is_rinshan=False)
    out = format_game_event(ev)
    assert "自摸和了" in out


def test_format_tsumo_rinshan() -> None:
    ev = TsumoEvent(seat=2, sequence=9, win_tile=Tile(Suit.SOU, 2), is_rinshan=True)
    out = format_game_event(ev)
    assert "岭上" in out


def test_format_flow_with_tenpai() -> None:
    ev = FlowEvent(seat=None, sequence=10, flow_kind=FlowKind.EXHAUSTED, tenpai_seats=frozenset({0, 2}))
    out = format_game_event(ev)
    assert "流局" in out
    assert "荒牌流局" in out
    assert "听牌" in out


def test_format_flow_three_ron() -> None:
    ev = FlowEvent(seat=None, sequence=11, flow_kind=FlowKind.THREE_RON, tenpai_seats=frozenset())
    out = format_game_event(ev)
    assert "三家和" in out


def test_format_hand_over_with_winners() -> None:
    wl = WinSettlementLine(seat=0, win_kind="tsumo", han=2, fu=30, hand_pattern="一般形", yakus=("断幺九", "ドラ"), points=2000)
    ev = HandOverEvent(seat=None, sequence=12, winners=(0,), payments=(2000, -700, -700, -600), win_lines=(wl,))
    out = format_game_event(ev)
    assert "和了" in out
    assert "断幺九" in out
    assert "2000" in out


def test_format_hand_over_no_winners() -> None:
    ev = HandOverEvent(seat=None, sequence=13, winners=(), payments=(0, 0, 0, 0))
    out = format_game_event(ev)
    assert "和了者无" in out


def test_format_match_end() -> None:
    ev = MatchEndEvent(seat=None, sequence=14, ranking=(1, 2, 3, 4), final_scores=(45000, 30000, 15000, 10000))
    out = format_game_event(ev)
    assert "比赛结束" in out
    assert "1位" in out
    assert "45000" in out


def test_format_game_event_unhandled() -> None:
    """基类 GameEvent 不属于任何子类，返回 None。"""
    from kernel.event_log import GameEvent

    ev = GameEvent(seat=0, sequence=99)
    assert format_game_event(ev) is None


# ── format_action_wire_supplement ────────────────────────────────────────────

def test_format_action_wire_supplement_noop_with_wall() -> None:
    out = format_action_wire_supplement({"kind": "noop", "wall": ["1m", "2m"]})
    assert "新一局" in out


def test_format_action_wire_supplement_noop_no_wall() -> None:
    assert format_action_wire_supplement({"kind": "noop"}) is None


def test_format_action_wire_supplement_begin_round() -> None:
    assert format_action_wire_supplement({"kind": "begin_round"}) is None


def test_format_action_wire_supplement_unknown() -> None:
    assert format_action_wire_supplement({"kind": "other"}) is None


# ── append_simple_log_block ──────────────────────────────────────────────────

def test_append_simple_log_block_fp_none() -> None:
    """fp=None 不应抛异常。"""
    append_simple_log_block(None, ())


def test_append_simple_log_block_with_events() -> None:
    buf = io.StringIO()
    ev = DrawTileEvent(seat=0, sequence=0, tile=Tile(Suit.MAN, 3), is_rinshan=False, wall_remaining=70)
    append_simple_log_block(buf, (ev,))
    assert "3m" in buf.getvalue()


def test_append_simple_log_block_drained_calls() -> None:
    buf = io.StringIO()
    append_simple_log_block(buf, (), drained_calls=5)
    assert "过牌 5 次" in buf.getvalue()


def test_append_simple_log_block_drained_zero() -> None:
    """drained_calls=0 不输出。"""
    buf = io.StringIO()
    append_simple_log_block(buf, (), drained_calls=0)
    assert buf.getvalue() == ""


def test_append_simple_log_block_supplement_when_no_events() -> None:
    buf = io.StringIO()
    append_simple_log_block(buf, (), action_wire={"kind": "noop", "wall": ["1m"]})
    assert "新一局" in buf.getvalue()


def test_append_simple_log_block_no_supplement_with_events() -> None:
    """有事件时不输出 action_wire 补充，避免与 RoundBegin 重复。"""
    buf = io.StringIO()
    ev = DrawTileEvent(seat=0, sequence=0, tile=Tile(Suit.MAN, 3), is_rinshan=False, wall_remaining=70)
    append_simple_log_block(buf, (ev,), action_wire={"kind": "noop", "wall": ["1m"]})
    text = buf.getvalue()
    assert "新一局" not in text
