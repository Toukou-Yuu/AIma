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
)
from llm.runner import run_llm_match


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
    rr = run_llm_match(seed=5, max_player_steps=120, dry_run=True)
    assert rr.actions_wire
    doc = rr.as_match_log()
    actions = actions_from_match_log(doc)
    final, _ = replay_from_actions(actions)
    assert final.phase == rr.final_state.phase
