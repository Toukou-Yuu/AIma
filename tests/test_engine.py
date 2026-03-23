"""Tests for engine phase shell and apply."""

from __future__ import annotations

import pytest

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    GameState,
    IllegalActionError,
    Suit,
    TableSnapshot,
    Tile,
    TurnPhase,
    apply,
    build_deck,
    initial_game_state,
    initial_table_snapshot,
    shuffle_deck,
)
from tests.call_helpers import clear_call_window_state


def _wall136(*, seed: int = 0):
    return tuple(shuffle_deck(build_deck(), seed=seed))


def test_initial_game_state_default_table() -> None:
    g = initial_game_state()
    assert g.phase == GamePhase.PRE_DEAL
    assert isinstance(g.table, TableSnapshot)
    assert g.board is None


def test_initial_game_state_custom_table() -> None:
    t = initial_table_snapshot(dealer_seat=2)
    g = initial_game_state(t)
    assert g.table.dealer_seat == 2
    assert g.board is None


def test_begin_round_pre_deal_to_in_round_with_board() -> None:
    g0 = initial_game_state()
    w = _wall136(seed=11)
    out = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w))
    assert out.new_state.phase == GamePhase.IN_ROUND
    assert out.new_state.table == g0.table
    assert out.new_state.board is not None
    assert out.new_state.board.hands[g0.table.dealer_seat].total() == 14
    # K13: 验证生成 RoundBeginEvent
    assert len(out.events) == 1
    event = out.events[0]
    assert event.dealer_seat == g0.table.dealer_seat
    assert event.dora_indicator is not None
    assert event.seeds == (0, 13, 26, 39)


def test_begin_round_requires_wall() -> None:
    g = initial_game_state()
    with pytest.raises(IllegalActionError, match="136"):
        apply(g, Action(ActionKind.BEGIN_ROUND))


def test_begin_round_invalid_wall_length() -> None:
    g = initial_game_state()
    with pytest.raises(IllegalActionError, match="136"):
        apply(g, Action(ActionKind.BEGIN_ROUND, wall=tuple(build_deck())[:100]))


def test_begin_round_invalid_multiset() -> None:
    bad = tuple(Tile(Suit.MAN, 1, False) for _ in range(136))
    g = initial_game_state()
    with pytest.raises(IllegalActionError, match="multiset"):
        apply(g, Action(ActionKind.BEGIN_ROUND, wall=bad))


def test_noop_in_round_is_identity() -> None:
    g0 = initial_game_state()
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=_wall136(seed=3))).new_state
    out = apply(g1, Action(ActionKind.NOOP))
    assert out.new_state is g1
    assert out.events == ()  # NOOP 不生成事件


def test_noop_in_pre_deal_raises() -> None:
    g = initial_game_state()
    with pytest.raises(IllegalActionError, match="not allowed"):
        apply(g, Action(ActionKind.NOOP))


def test_begin_round_in_round_raises() -> None:
    g0 = initial_game_state()
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=_wall136())).new_state
    with pytest.raises(IllegalActionError, match="not allowed"):
        apply(g1, Action(ActionKind.BEGIN_ROUND, wall=_wall136(seed=1)))


def test_unwired_phase_raises() -> None:
    g = GameState(phase=GamePhase.CALL_RESPONSE, table=initial_table_snapshot(), board=None)
    with pytest.raises(IllegalActionError, match="no implemented transitions"):
        apply(g, Action(ActionKind.NOOP))


def test_invalid_action_seat_raises() -> None:
    g = initial_game_state()
    with pytest.raises(IllegalActionError, match="seat"):
        apply(g, Action(ActionKind.BEGIN_ROUND, wall=_wall136(), seat=4))


def _in_round_after_deal(*, seed: int = 12):
    g0 = initial_game_state()
    return apply(g0, Action(ActionKind.BEGIN_ROUND, wall=_wall136(seed=seed))).new_state


def test_apply_discard_draw_cycle_via_engine() -> None:
    g = _in_round_after_deal(seed=13)
    b = g.board
    assert b is not None
    ds = g.table.dealer_seat
    assert b.turn_phase == TurnPhase.MUST_DISCARD
    t0 = next(iter(b.hands[ds].elements()))
    g1 = apply(
        g,
        Action(ActionKind.DISCARD, seat=ds, tile=t0),
    ).new_state
    g1 = clear_call_window_state(g1)
    b1 = g1.board
    assert b1 is not None
    assert b1.turn_phase == TurnPhase.NEED_DRAW
    assert b1.current_seat == (ds + 1) % 4
    g2 = apply(g1, Action(ActionKind.DRAW, seat=b1.current_seat)).new_state
    b2 = g2.board
    assert b2 is not None
    assert b2.turn_phase == TurnPhase.MUST_DISCARD
    assert b2.last_draw_tile is not None


def test_apply_draw_omitted_seat_uses_current() -> None:
    g = _in_round_after_deal(seed=14)
    b = g.board
    assert b is not None
    d0 = next(iter(b.hands[b.current_seat].elements()))
    g1 = apply(g, Action(ActionKind.DISCARD, seat=b.current_seat, tile=d0)).new_state
    g1 = clear_call_window_state(g1)
    g2 = apply(g1, Action(ActionKind.DRAW)).new_state
    assert g2.board is not None
    assert g2.board.turn_phase == TurnPhase.MUST_DISCARD


def test_apply_discard_requires_tile_and_seat() -> None:
    g = _in_round_after_deal(seed=15)
    b = g.board
    assert b is not None
    with pytest.raises(IllegalActionError, match="tile"):
        apply(g, Action(ActionKind.DISCARD, seat=b.current_seat))
    with pytest.raises(IllegalActionError, match="seat"):
        apply(
            g,
            Action(
                ActionKind.DISCARD, seat=None, tile=next(iter(b.hands[b.current_seat].elements()))
            ),
        )


def test_apply_draw_wrong_seat_raises() -> None:
    g = _in_round_after_deal(seed=16)
    b = g.board
    assert b is not None
    d0 = next(iter(b.hands[b.current_seat].elements()))
    g1 = apply(g, Action(ActionKind.DISCARD, seat=b.current_seat, tile=d0)).new_state
    g1 = clear_call_window_state(g1)
    wrong = (g1.board.current_seat + 1) % 4 if g1.board else 0
    with pytest.raises(IllegalActionError, match="current_seat"):
        apply(g1, Action(ActionKind.DRAW, seat=wrong))
