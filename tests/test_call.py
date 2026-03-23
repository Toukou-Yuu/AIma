"""舍牌应答与荣和（七对子）探测。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    GameState,
    IllegalActionError,
    Suit,
    Tile,
    apply,
    build_deck,
    initial_game_state,
    initial_table_snapshot,
    shuffle_deck,
)
from kernel.call.transitions import apply_pass_call, apply_ron
from kernel.call.win import can_ron_seven_pairs
from kernel.deal.model import BoardState
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from tests.test_scoring import _board_sorted_deal, _pool_not_in_wall, _take_n


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


def _board_seven_pairs_ron_window() -> BoardState:
    """seat0 打 7m；seat1 门清七对听 7m；荣和阶段未结束。"""
    b0 = _board_sorted_deal(dealer=0)
    pool = _pool_not_in_wall(b0)
    t7 = Tile(Suit.MAN, 7)
    hand1 = Counter()
    for r in range(1, 7):
        t = Tile(Suit.MAN, r)
        for _ in range(2):
            assert pool[t] >= 1
            pool[t] -= 1
            if pool[t] == 0:
                del pool[t]
            hand1[t] += 1
    pool[t7] -= 1
    hand1[t7] += 1
    assert pool[t7] >= 1
    pool[t7] -= 1
    if pool[t7] == 0:
        del pool[t7]
    new_hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == 1:
            new_hands.append(hand1)
        else:
            new_hands.append(_take_n(pool, 13))
    assert sum(pool.values()) == 0
    river = (RiverEntry(0, t7),)
    cs = CallResolution.initial_after_discard(0, 0, t7)
    return BoardState(
        hands=tuple(new_hands),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=0,
        turn_phase=TurnPhase.CALL_RESPONSE,
        river=river,
        melds=b0.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=cs,
    )


def test_ron_allowed_when_not_passed_same_tile() -> None:
    b = _board_seven_pairs_ron_window()
    b2 = apply_ron(b, 1)
    assert b2.call_state is not None
    assert 1 in b2.call_state.ron_claimants


def test_same_turn_furiten_after_pass_then_ron() -> None:
    b = _board_seven_pairs_ron_window()
    b_pass = apply_pass_call(b, 1)
    with pytest.raises(ValueError, match="同巡振听"):
        apply_ron(b_pass, 1)


def test_same_turn_furiten_via_engine_illegal_action() -> None:
    b = _board_seven_pairs_ron_window()
    gs = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    g2 = apply(gs, Action(ActionKind.PASS_CALL, seat=1)).new_state
    with pytest.raises(IllegalActionError, match="同巡振听"):
        apply(g2, Action(ActionKind.RON, seat=1))


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
