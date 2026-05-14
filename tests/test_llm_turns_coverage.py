"""turns.py pending_actor_seats 各分支覆盖。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.board import CallResolution, TurnPhase
from kernel.table import initial_table_snapshot
from tests.engine_helpers import board_sorted_deal, make_board_with_discard
from tests.call_helpers import clear_call_window
from llm.turns import pending_actor_seats


def _make_table():
    return initial_table_snapshot()


def _make_state(phase: GamePhase, board=None) -> GameState:
    return GameState(phase=phase, table=_make_table(), board=board)


# ── MATCH_END ────────────────────────────────────────────────────────────────

def test_match_end_returns_empty() -> None:
    state = _make_state(GamePhase.MATCH_END)
    assert pending_actor_seats(state) == []


# ── HAND_OVER / FLOWN ───────────────────────────────────────────────────────

def test_hand_over_returns_empty() -> None:
    state = _make_state(GamePhase.HAND_OVER)
    assert pending_actor_seats(state) == []


def test_flown_returns_empty() -> None:
    state = _make_state(GamePhase.FLOWN)
    assert pending_actor_seats(state) == []


# ── IN_ROUND but board is None ───────────────────────────────────────────────

def test_in_round_no_board_returns_empty() -> None:
    state = _make_state(GamePhase.IN_ROUND, board=None)
    assert pending_actor_seats(state) == []


# ── IN_ROUND + NEED_DRAW ────────────────────────────────────────────────────

def test_need_draw_returns_current_seat() -> None:
    b = board_sorted_deal(dealer=0)
    tile = next(iter(b.hands[0]))
    b2 = make_board_with_discard(dealer=0, discarder=0, discard_tile=tile, discarder_hand=b.hands[0])
    b3 = clear_call_window(b2)
    assert b3.turn_phase == TurnPhase.NEED_DRAW
    state = _make_state(GamePhase.IN_ROUND, board=b3)
    assert pending_actor_seats(state) == [b3.current_seat]


# ── IN_ROUND + MUST_DISCARD ─────────────────────────────────────────────────

def test_must_discard_returns_current_seat() -> None:
    b = board_sorted_deal(dealer=0)
    state = _make_state(GamePhase.IN_ROUND, board=b)
    assert pending_actor_seats(state) == [b.current_seat]


# ── IN_ROUND + CALL_RESPONSE ────────────────────────────────────────────────

def test_call_response_returns_current_seat() -> None:
    b = board_sorted_deal(dealer=0)
    tile = next(iter(b.hands[0]))
    b2 = make_board_with_discard(dealer=0, discarder=0, discard_tile=tile, discarder_hand=b.hands[0])
    assert b2.turn_phase == TurnPhase.CALL_RESPONSE
    state = _make_state(GamePhase.IN_ROUND, board=b2)
    result = pending_actor_seats(state)
    assert len(result) > 0


# ── PRE_DEAL (not IN_ROUND, not terminal) ───────────────────────────────────

def test_pre_deal_returns_empty() -> None:
    state = _make_state(GamePhase.PRE_DEAL)
    assert pending_actor_seats(state) == []
