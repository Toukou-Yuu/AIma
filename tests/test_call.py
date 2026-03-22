"""舍牌应答与荣和（七对子）探测。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    IllegalActionError,
    Suit,
    Tile,
    apply,
    build_deck,
    initial_game_state,
    shuffle_deck,
)
from kernel.call.win import can_ron_seven_pairs


def test_seven_pairs_detector() -> None:
    c: Counter[Tile] = Counter()
    for r in range(1, 7):
        c[Tile(Suit.MAN, r, False)] = 2
    c[Tile(Suit.MAN, 7, False)] = 1
    win = Tile(Suit.MAN, 7, False)
    assert can_ron_seven_pairs(c, (), win) is True
    assert can_ron_seven_pairs(c, (), Tile(Suit.MAN, 8, False)) is False


def test_ron_rejected_when_shape_wrong() -> None:
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=13))
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    b = g1.board
    assert b is not None
    ds = b.current_seat
    t0 = next(iter(b.hands[ds].elements()))
    g2 = apply(g1, Action(ActionKind.DISCARD, seat=ds, tile=t0)).new_state
    cs = g2.board.call_state
    assert cs is not None
    s = next(iter(cs.ron_remaining))
    with pytest.raises(IllegalActionError, match="illegal ron"):
        apply(g2, Action(ActionKind.RON, seat=s))


def test_draw_illegal_during_call_response() -> None:
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=14))
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    b = g1.board
    assert b is not None
    d0 = next(iter(b.hands[b.current_seat].elements()))
    g2 = apply(g1, Action(ActionKind.DISCARD, seat=b.current_seat, tile=d0)).new_state
    with pytest.raises(IllegalActionError, match="CALL_RESPONSE"):
        apply(g2, Action(ActionKind.DRAW))


def test_pass_call_chain_via_engine_reaches_need_draw() -> None:
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=15))
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    b = g1.board
    assert b is not None
    d0 = next(iter(b.hands[b.current_seat].elements()))
    g2 = apply(g1, Action(ActionKind.DISCARD, seat=b.current_seat, tile=d0)).new_state
    g = g2
    while g.board is not None and g.board.call_state is not None:
        cs = g.board.call_state
        assert cs is not None
        if cs.stage == "ron":
            s = next(iter(cs.ron_remaining))
        elif cs.stage == "pon_kan":
            s = cs.pon_kan_order[cs.pon_kan_idx]
        else:
            from kernel.play.model import kamicha_seat

            s = kamicha_seat(cs.discard_seat)
        g = apply(g, Action(ActionKind.PASS_CALL, seat=s)).new_state
    assert g.board is not None
    assert g.board.turn_phase.name == "NEED_DRAW"
    assert g.phase == GamePhase.IN_ROUND
