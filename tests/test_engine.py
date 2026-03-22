"""Tests for engine phase shell and apply."""

from __future__ import annotations

import pytest

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    GameState,
    IllegalActionError,
    TableSnapshot,
    apply,
    initial_game_state,
    initial_table_snapshot,
)


def test_initial_game_state_default_table() -> None:
    g = initial_game_state()
    assert g.phase == GamePhase.PRE_DEAL
    assert isinstance(g.table, TableSnapshot)


def test_initial_game_state_custom_table() -> None:
    t = initial_table_snapshot(dealer_seat=2)
    g = initial_game_state(t)
    assert g.table.dealer_seat == 2


def test_begin_round_stub_pre_deal_to_in_round() -> None:
    g0 = initial_game_state()
    out = apply(g0, Action(ActionKind.BEGIN_ROUND_STUB))
    assert out.new_state.phase == GamePhase.IN_ROUND
    assert out.new_state.table == g0.table
    assert out.events == ()


def test_noop_in_round_is_identity() -> None:
    g0 = initial_game_state()
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND_STUB)).new_state
    out = apply(g1, Action(ActionKind.NOOP))
    assert out.new_state is g1
    assert out.events == ()


def test_noop_in_pre_deal_raises() -> None:
    g = initial_game_state()
    with pytest.raises(IllegalActionError, match="not allowed"):
        apply(g, Action(ActionKind.NOOP))


def test_begin_round_stub_in_round_raises() -> None:
    g0 = initial_game_state()
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND_STUB)).new_state
    with pytest.raises(IllegalActionError, match="not allowed"):
        apply(g1, Action(ActionKind.BEGIN_ROUND_STUB))


def test_unwired_phase_raises() -> None:
    g = GameState(phase=GamePhase.CALL_RESPONSE, table=initial_table_snapshot())
    with pytest.raises(IllegalActionError, match="no implemented transitions"):
        apply(g, Action(ActionKind.NOOP))


def test_invalid_action_seat_raises() -> None:
    g = initial_game_state()
    with pytest.raises(IllegalActionError, match="seat"):
        apply(g, Action(ActionKind.BEGIN_ROUND_STUB, seat=4))
