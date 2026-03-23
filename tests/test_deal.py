"""Tests for initial deal and board state."""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    INITIAL_DEAL_TILES,
    LIVE_WALL_AFTER_DEAL,
    Suit,
    Tile,
    TurnPhase,
    assert_wall_is_standard_deck,
    build_board_after_split,
    build_deck,
    shuffle_deck,
    split_wall,
)


def _shuffled_wall(*, seed: int = 0) -> tuple[Tile, ...]:
    return tuple(shuffle_deck(build_deck(), seed=seed))


def test_build_board_hand_counts() -> None:
    ws = split_wall(_shuffled_wall(seed=1))
    b = build_board_after_split(ws, dealer_seat=0)
    counts = sorted(sum(h.values()) for h in b.hands)
    assert counts == [13, 13, 13, 14]
    assert b.hands[0].total() == 14
    assert b.current_seat == 0
    assert b.turn_phase == TurnPhase.MUST_DISCARD
    assert b.river == ()
    assert b.last_draw_tile is None


def test_build_board_dealer_seat_2() -> None:
    ws = split_wall(_shuffled_wall(seed=2))
    b = build_board_after_split(ws, dealer_seat=2)
    assert b.hands[2].total() == 14
    for s in (0, 1, 3):
        assert b.hands[s].total() == 13
    assert b.current_seat == 2
    assert b.turn_phase == TurnPhase.MUST_DISCARD


def test_live_wall_length_and_index() -> None:
    ws = split_wall(_shuffled_wall())
    b = build_board_after_split(ws, dealer_seat=0)
    assert len(b.live_wall) == LIVE_WALL_AFTER_DEAL
    assert b.live_draw_index == 0


def test_multiset_conservation() -> None:
    ws = split_wall(_shuffled_wall(seed=7))
    b = build_board_after_split(ws, dealer_seat=1)
    acc: Counter[Tile] = Counter()
    for h in b.hands:
        acc.update(h)
    acc.update(b.live_wall)
    acc.update(b.dead_wall.rinshan)
    acc.update(b.dead_wall.ura_bases)
    acc.update(b.dead_wall.indicators)
    assert acc == Counter(build_deck())


def test_revealed_indicator_is_first_slot() -> None:
    ws = split_wall(_shuffled_wall(seed=3))
    b = build_board_after_split(ws, dealer_seat=0)
    assert b.revealed_indicators == (ws.dead.indicators[0],)


def test_determinism_codes() -> None:
    ws = split_wall(_shuffled_wall(seed=99))
    b0 = build_board_after_split(ws, dealer_seat=0)
    ws2 = split_wall(_shuffled_wall(seed=99))
    b1 = build_board_after_split(ws2, dealer_seat=0)
    for i in range(4):
        assert sorted(t.to_code() for t in b0.hands[i].elements()) == sorted(
            t.to_code() for t in b1.hands[i].elements()
        )
    assert [t.to_code() for t in b0.live_wall] == [t.to_code() for t in b1.live_wall]
    assert b0.revealed_indicators[0].to_code() == b1.revealed_indicators[0].to_code()


def test_assert_wall_wrong_length() -> None:
    with pytest.raises(ValueError, match="136"):
        assert_wall_is_standard_deck(tuple(build_deck())[:135])


def test_assert_wall_bad_multiset() -> None:
    # 136 张同牌，多重集合必与标准牌山不符
    bad = tuple(Tile(Suit.MAN, 1, False) for _ in range(136))
    with pytest.raises(ValueError, match="multiset"):
        assert_wall_is_standard_deck(bad)


def test_deal_uses_first_53_of_live() -> None:
    ws = split_wall(_shuffled_wall(seed=5))
    b = build_board_after_split(ws, dealer_seat=0)
    flat: list[str] = []
    for h in b.hands:
        flat.extend(sorted(t.to_code() for t in h.elements()))
    live_head = [t.to_code() for t in ws.live[:INITIAL_DEAL_TILES]]
    assert sorted(live_head) == sorted(flat)
