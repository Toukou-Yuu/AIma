"""``replay_json`` 牌谱 wire 与跑局日志可回放性。"""

from __future__ import annotations

from kernel import (
    Action,
    ActionKind,
    apply,
    build_deck,
    initial_game_state,
    shuffle_deck,
)
from kernel.event_log import HandOverEvent, MatchEndEvent, RoundBeginEvent, WinSettlementLine
from kernel.replay import replay_from_actions
from kernel.replay_json import (
    action_from_wire,
    action_to_wire,
    actions_from_match_log,
    game_event_from_wire,
    game_event_to_wire,
    match_log_document,
)
from llm.config import MatchEndCondition
from llm.runner import run_llm_match
from tests.llm_test_utils import load_test_runtime_config, load_test_seat_llm_configs


def _wall(*, seed: int) -> tuple:
    return tuple(shuffle_deck(build_deck(), seed=seed))


def test_action_round_trip_begin_round_wall() -> None:
    g0 = initial_game_state()
    w = _wall(seed=41)
    a0 = Action(ActionKind.BEGIN_ROUND, wall=w)
    wdict = action_to_wire(a0)
    a1 = action_from_wire(wdict)
    assert a1 == a0
    g1 = apply(g0, a1).new_state
    assert g1.board is not None


def test_action_round_trip_call_pass_drain() -> None:
    a0 = Action(ActionKind.CALL_PASS_DRAIN)
    a1 = action_from_wire(action_to_wire(a0))
    assert a1 == a0


def test_action_round_trip_discard() -> None:
    g0 = initial_game_state()
    w = _wall(seed=42)
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    b = g1.board
    assert b is not None
    tile = next(iter(b.hands[b.current_seat].elements()))
    d0 = Action(ActionKind.DISCARD, seat=b.current_seat, tile=tile)
    d1 = action_from_wire(action_to_wire(d0))
    assert d1 == d0


def test_game_event_round_trip_round_begin() -> None:
    g0 = initial_game_state()
    w = _wall(seed=43)
    out = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))
    assert len(out.events) == 1
    ev = out.events[0]
    assert isinstance(ev, RoundBeginEvent)
    wire = game_event_to_wire(ev)
    ev2 = game_event_from_wire(wire)
    assert ev2 == ev


def test_hand_over_event_round_trip_with_win_lines() -> None:
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
        sequence=5,
        winners=(1,),
        payments=(-2900, 2900, 0, 0),
        win_lines=(line,),
    )
    wire = game_event_to_wire(ev)
    ev2 = game_event_from_wire(wire)
    assert ev2 == ev


def test_match_end_event_round_trip() -> None:
    ev = MatchEndEvent(
        seat=None,
        sequence=99,
        ranking=(1, 2, 3, 4),
        final_scores=(35000, 25000, 20000, 20000),
    )
    wire = game_event_to_wire(ev)
    ev2 = game_event_from_wire(wire)
    assert ev2 == ev


def test_run_llm_match_log_replays_same_phase() -> None:
    match_end = MatchEndCondition(type="hands", value=8, allow_negative=False)
    runtime = load_test_runtime_config()
    rr = run_llm_match(
        seed=5,
        match_end=match_end,
        dry_run=True,
        request_delay_seconds=0.0,
        history_budget=runtime.history_budget,
        context_scope=runtime.context_scope,
        compression_level=runtime.compression_level,
        context_compression_threshold=runtime.context_compression_threshold,
        seat_llm_configs=load_test_seat_llm_configs(),
        prompt_format=runtime.prompt_format,
        enable_conversation_logging=runtime.conversation_logging_enabled,
    )
    assert rr.actions_wire
    doc = rr.as_match_log()
    actions = actions_from_match_log(doc)
    final, _ = replay_from_actions(actions)
    assert final.phase == rr.final_state.phase


def test_match_log_document_with_players() -> None:
    """match_log_document() 输出包含 players 字段。"""
    players_wire = (
        {"id": "ichihime", "seat": 0, "name": "一姬"},
        {"id": "yui", "seat": 1, "name": "八木唯"},
    )
    doc = match_log_document(
        seed=42,
        stopped_reason="match_end",
        steps=100,
        final_phase="match_end",
        actions_wire=(),
        events_wire=(),
        players=players_wire,
    )
    assert "players" in doc
    assert len(doc["players"]) == 2
    assert doc["players"][0]["id"] == "ichihime"
    assert doc["players"][1]["name"] == "八木唯"


def test_match_log_document_without_players() -> None:
    """players 为空时不输出字段。"""
    doc = match_log_document(
        seed=42,
        stopped_reason="match_end",
        steps=100,
        final_phase="match_end",
        actions_wire=(),
        events_wire=(),
        players=(),
    )
    assert "players" not in doc


def test_match_log_document_players_none() -> None:
    """players=None 时不输出字段。"""
    doc = match_log_document(
        seed=42,
        stopped_reason="match_end",
        steps=100,
        final_phase="match_end",
        actions_wire=(),
        events_wire=(),
        players=None,
    )
    assert "players" not in doc


def test_actions_from_match_log_ignores_players() -> None:
    """players 字段不影响 actions 解析。"""
    doc = {
        "format_version": 2,
        "seed": 42,
        "actions": [{"kind": "call_pass_drain"}],
        "players": [
            {"id": "ichihime", "seat": 0, "name": "一姬"},
            {"id": "yui", "seat": 1, "name": "八木唯"},
        ],
    }
    actions = actions_from_match_log(doc)
    assert len(actions) == 1
    assert actions[0].kind == ActionKind.CALL_PASS_DRAIN


def test_actions_from_match_log_old_format_without_players() -> None:
    """旧牌谱（无 players 字段）仍可正确解析。"""
    doc_old = {
        "format_version": 2,
        "seed": 42,
        "actions": [{"kind": "call_pass_drain"}],
    }
    actions = actions_from_match_log(doc_old)
    assert len(actions) == 1
    assert actions[0].kind == ActionKind.CALL_PASS_DRAIN
