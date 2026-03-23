"""自摸和了与点棒结算（引擎接线）。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    BoardState,
    GamePhase,
    IllegalActionError,
    Suit,
    Tile,
    TurnPhase,
    apply,
    build_board_after_split,
    build_deck,
    initial_table_snapshot,
    split_wall,
)
from kernel.engine.state import GameState
from kernel.scoring.points import child_tsumo_payments
from kernel.scoring.dora import ura_indicators_for_settlement
from kernel.scoring.settle import settle_tsumo_table


def _board_sorted_deal(*, dealer: int = 0) -> BoardState:
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def _pool_not_in_wall(b0: BoardState) -> Counter[Tile]:
    rem = Counter(b0.live_wall[b0.live_draw_index :])
    rem.update(b0.dead_wall.rinshan)
    rem.update(b0.dead_wall.ura_bases)
    rem.update(b0.dead_wall.indicators)
    pool = Counter(build_deck())
    for t, n in rem.items():
        pool[t] -= n
    assert sum(pool.values()) == 53
    return pool


def _take_n(pool: Counter[Tile], n: int) -> Counter[Tile]:
    out = Counter()
    for _ in range(n):
        x = next(iter(pool.elements()))
        out[x] += 1
        pool[x] -= 1
        if pool[x] == 0:
            del pool[x]
    return out


def _must_discard_chiitoitsu_tsumo_s1() -> BoardState:
    """seat1：14 张七对子含两枚 7m，上一张自摸为 7m。"""
    b0 = _board_sorted_deal(dealer=0)
    pool = _pool_not_in_wall(b0)
    t7 = Tile(Suit.MAN, 7)
    hand1 = Counter()
    for r in range(1, 7):
        t = Tile(Suit.MAN, r)
        for _ in range(2):
            pool[t] -= 1
            hand1[t] += 1
    for _ in range(2):
        pool[t7] -= 1
        hand1[t7] += 1
    new_hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == 1:
            new_hands.append(hand1)
            continue
        new_hands.append(_take_n(pool, 13))
    assert sum(pool.values()) == 0
    return BoardState(
        hands=tuple(new_hands),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=1,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b0.river,
        melds=b0.melds,
        last_draw_tile=t7,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=None,
    )


def test_apply_tsumo_chiitoitsu_hand_over_and_scores() -> None:
    b = _must_discard_chiitoitsu_tsumo_s1()
    tab = initial_table_snapshot()
    g = GameState(phase=GamePhase.IN_ROUND, table=tab, board=b)
    out = apply(g, Action(ActionKind.TSUMO, seat=1))
    assert out.new_state.phase == GamePhase.HAND_OVER
    assert out.new_state.ron_winners == frozenset({1})
    ura = ura_indicators_for_settlement(b.dead_wall, len(b.revealed_indicators))
    exp = settle_tsumo_table(
        tab,
        b,
        winner=1,
        win_tile=Tile(Suit.MAN, 7),
        ura_indicators=ura,
    )
    assert out.new_state.table.scores == exp.scores
    assert out.new_state.table.kyoutaku == 0


def test_tsumo_rejected_without_last_draw() -> None:
    b0 = _board_sorted_deal()
    b = BoardState(
        hands=b0.hands,
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=b0.current_seat,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b0.river,
        melds=b0.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=None,
    )
    g = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    with pytest.raises(IllegalActionError, match="last_draw_tile"):
        apply(g, Action(ActionKind.TSUMO, seat=b.current_seat))


def test_child_tsumo_payments_sum_zero() -> None:
    d = child_tsumo_payments(winner=1, dealer=0, fu=40, han=2, honba=0)
    assert sum(d.values()) == 0
