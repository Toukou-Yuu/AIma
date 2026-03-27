"""调度与 dry-run 跑局。"""

from __future__ import annotations

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    apply,
    build_deck,
    initial_game_state,
    shuffle_deck,
)
from llm.runner import run_llm_match
from llm.turns import pending_actor_seats


def test_pending_after_begin_round() -> None:
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=99))
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    assert g1.phase == GamePhase.IN_ROUND
    assert g1.board is not None
    pending = pending_actor_seats(g1)
    assert pending == [g1.board.current_seat]


def test_run_llm_match_dry_run_advances() -> None:
    rr = run_llm_match(seed=7, max_steps=80, dry_run=True)
    assert rr.steps > 0
    assert rr.final_state.phase in (
        GamePhase.IN_ROUND,
        GamePhase.HAND_OVER,
        GamePhase.FLOWN,
        GamePhase.MATCH_END,
    )
