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
    apply,
    build_deck,
    initial_game_state,
    initial_table_snapshot,
    shuffle_deck,
)


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
    assert out.events == ()


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
    assert out.events == ()


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
