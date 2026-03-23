"""Tests for draw/discard loop and river."""

from __future__ import annotations

import pytest

from kernel import (
    TurnPhase,
    apply_discard,
    apply_draw,
    build_board_after_split,
    build_deck,
    shuffle_deck,
    split_wall,
)
from tests.call_helpers import clear_call_window


def _board(*, seed: int = 0, dealer: int = 0):
    w = tuple(shuffle_deck(build_deck(), seed=seed))
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def _pick_any_tile(hand):
    return next(iter(hand.elements()))


def test_conservation_after_discard_and_draw() -> None:
    b0 = _board(seed=11)
    t0 = _pick_any_tile(b0.hands[b0.current_seat])
    b1 = apply_discard(b0, b0.current_seat, t0)
    assert b1.turn_phase == TurnPhase.CALL_RESPONSE
    b1 = clear_call_window(b1)
    assert b1.turn_phase == TurnPhase.NEED_DRAW
    b2 = apply_draw(b1, b1.current_seat)
    assert b2.turn_phase == TurnPhase.MUST_DISCARD
    in_hand = sum(sum(h.values()) for h in b2.hands)
    live_left = len(b2.live_wall) - b2.live_draw_index
    dead_n = (
        len(b2.dead_wall.rinshan)
        + len(b2.dead_wall.ura_bases)
        + len(b2.dead_wall.indicators)
    )
    assert in_hand + len(b2.river) + live_left + dead_n == 136


def test_dealer_must_discard_first_then_counterclockwise() -> None:
    b = _board(seed=3, dealer=1)
    assert b.current_seat == 1
    assert b.turn_phase == TurnPhase.MUST_DISCARD
    t = _pick_any_tile(b.hands[1])
    b = apply_discard(b, 1, t)
    assert b.current_seat == 2
    assert b.turn_phase == TurnPhase.CALL_RESPONSE
    b = clear_call_window(b)
    assert b.turn_phase == TurnPhase.NEED_DRAW
    b = apply_draw(b, 2)
    assert b.current_seat == 2
    assert b.turn_phase == TurnPhase.MUST_DISCARD


def test_tsumogiri_flag_on_river() -> None:
    b = _board(seed=5, dealer=0)
    d0 = _pick_any_tile(b.hands[0])
    b = apply_discard(b, 0, d0)
    b = clear_call_window(b)
    b = apply_draw(b, b.current_seat)
    drawn = b.last_draw_tile
    assert drawn is not None
    b = apply_discard(b, b.current_seat, drawn)
    b = clear_call_window(b)
    assert b.river[-1].tsumogiri is True


def test_hand_discard_not_tsumogiri() -> None:
    b = _board(seed=6, dealer=0)
    d0 = _pick_any_tile(b.hands[0])
    b = apply_discard(b, 0, d0)
    b = clear_call_window(b)
    b = apply_draw(b, b.current_seat)
    drawn = b.last_draw_tile
    assert drawn is not None
    other = _pick_any_tile(b.hands[b.current_seat])
    if other == drawn:
        # 换一张：手牌 14 张里至少有一张与摸牌不同（标准牌山）
        for t in b.hands[b.current_seat].elements():
            if t != drawn:
                other = t
                break
    assert other != drawn
    b = apply_discard(b, b.current_seat, other)
    b = clear_call_window(b)
    assert b.river[-1].tsumogiri is False


def test_draw_wrong_seat_raises() -> None:
    b = _board(seed=7)
    d0 = _pick_any_tile(b.hands[0])
    b = apply_discard(b, 0, d0)
    b = clear_call_window(b)
    wrong = (b.current_seat + 1) % 4
    with pytest.raises(ValueError, match="current_seat"):
        apply_draw(b, wrong)


def test_discard_wrong_phase_raises() -> None:
    b = _board(seed=8)
    d0 = _pick_any_tile(b.hands[0])
    b = apply_discard(b, 0, d0)
    with pytest.raises(ValueError, match="MUST_DISCARD"):
        apply_discard(b, b.current_seat, _pick_any_tile(b.hands[b.current_seat]))


def test_discard_tile_not_in_hand_raises() -> None:
    b = _board(seed=9)
    seat = b.current_seat
    hand = b.hands[seat]
    t_bad = next(t for t in build_deck() if hand.get(t, 0) == 0)
    with pytest.raises(ValueError, match="not in hand"):
        apply_discard(b, seat, t_bad)


def test_wall_exhausted_draw_raises() -> None:
    b = _board(seed=10)
    while b.live_draw_index < len(b.live_wall):
        if b.turn_phase == TurnPhase.MUST_DISCARD:
            t = _pick_any_tile(b.hands[b.current_seat])
            b = apply_discard(b, b.current_seat, t)
            b = clear_call_window(b)
        else:
            b = apply_draw(b, b.current_seat)
    assert b.live_draw_index == len(b.live_wall)
    assert b.turn_phase == TurnPhase.MUST_DISCARD
    t = _pick_any_tile(b.hands[b.current_seat])
    b = apply_discard(b, b.current_seat, t)
    b = clear_call_window(b)
    assert b.turn_phase == TurnPhase.NEED_DRAW
    with pytest.raises(ValueError, match="exhausted"):
        apply_draw(b, b.current_seat)
