"""立直宣言、供托、摸切约束与一发标记。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    BoardState,
    GamePhase,
    IllegalActionError,
    Meld,
    MeldKind,
    RIICHI_STICK_POINTS,
    Suit,
    Tile,
    TurnPhase,
    apply,
    build_board_after_split,
    build_deck,
    initial_game_state,
    initial_table_snapshot,
    shuffle_deck,
    split_wall,
)
from kernel.engine.state import GameState
from kernel.play import apply_discard
from kernel.riichi.tenpai import is_tenpai_default, is_tenpai_seven_pairs
from kernel.table import TableSnapshot
from tests.call_helpers import clear_call_window_state


def _board(*, seed: int = 0, dealer: int = 0) -> BoardState:
    w = tuple(shuffle_deck(build_deck(), seed=seed))
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def _board_chiitoitsu_dealer() -> tuple[BoardState, Tile]:
    """
    亲 0：14 张门清，1m–6m 各对子 + 7m 对子；打掉一枚 7m 后为七对听牌（听 7m）。
    """
    b0 = _board(seed=0, dealer=0)
    merged: Counter[Tile] = Counter()
    for h in b0.hands:
        merged.update(h)
    d = 0
    hand_d: Counter[Tile] = Counter()
    for rank in range(1, 7):
        t = Tile(Suit.MAN, rank)
        for _ in range(2):
            merged[t] -= 1
            hand_d[t] += 1
    t7 = Tile(Suit.MAN, 7)
    for _ in range(2):
        merged[t7] -= 1
        hand_d[t7] += 1
    new_hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == d:
            new_hands.append(hand_d)
        else:
            take: Counter[Tile] = Counter()
            for _ in range(13):
                x = next(iter(merged.elements()))
                take[x] += 1
                merged[x] -= 1
            new_hands.append(take)
    assert sum(merged.values()) == 0
    b = BoardState(
        hands=tuple(new_hands),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=d,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b0.river,
        melds=b0.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=None,
    )
    return b, t7


def _board_standard_tenpai_dealer() -> tuple[BoardState, Tile]:
    """
    亲 0：14 张门清；打掉 9m 后为与 ``can_ron_default`` 对齐的标准形听牌。
    """
    b0 = _board(seed=0, dealer=0)
    merged: Counter[Tile] = Counter()
    for h in b0.hands:
        merged.update(h)
    d = 0
    hand_d: Counter[Tile] = Counter()
    for rank in range(1, 7):
        t = Tile(Suit.MAN, rank)
        merged[t] -= 1
        hand_d[t] += 1
    for rank in range(1, 6):
        t = Tile(Suit.PIN, rank)
        merged[t] -= 1
        hand_d[t] += 1
    t8 = Tile(Suit.SOU, 8)
    for _ in range(2):
        merged[t8] -= 1
        hand_d[t8] += 1
    t9 = Tile(Suit.MAN, 9)
    merged[t9] -= 1
    hand_d[t9] += 1
    new_hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == d:
            new_hands.append(hand_d)
        else:
            take: Counter[Tile] = Counter()
            for _ in range(13):
                x = next(iter(merged.elements()))
                take[x] += 1
                merged[x] -= 1
            new_hands.append(take)
    assert sum(merged.values()) == 0
    b = BoardState(
        hands=tuple(new_hands),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=d,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b0.river,
        melds=b0.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=None,
    )
    return b, t9


def test_is_tenpai_default_standard_form() -> None:
    c = Counter()
    for r in range(1, 7):
        c[Tile(Suit.MAN, r)] = 1
    for r in range(1, 6):
        c[Tile(Suit.PIN, r)] = 1
    c[Tile(Suit.SOU, 8)] = 2
    assert sum(c.values()) == 13
    assert is_tenpai_default(c, ()) is True


@pytest.mark.parametrize(
    ("tenpai", "ranks"),
    [
        (True, (1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7)),
        (False, (1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6)),
        (False, (1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 6)),
    ],
)
def test_is_tenpai_seven_pairs(tenpai: bool, ranks: tuple[int, ...]) -> None:
    c = Counter(Tile(Suit.MAN, r) for r in ranks)
    assert is_tenpai_seven_pairs(c, ()) is tenpai


def test_apply_riichi_standard_form_tenpai() -> None:
    b, t9 = _board_standard_tenpai_dealer()
    st = initial_table_snapshot()
    gs = GameState(phase=GamePhase.IN_ROUND, table=st, board=b)
    out = apply(
        gs,
        Action(ActionKind.DISCARD, seat=0, tile=t9, declare_riichi=True),
    )
    assert out.new_state.board is not None
    assert out.new_state.board.riichi[0] is True


def test_apply_riichi_updates_table_and_river() -> None:
    b, t7 = _board_chiitoitsu_dealer()
    st = initial_table_snapshot()
    gs = GameState(phase=GamePhase.IN_ROUND, table=st, board=b)
    out = apply(
        gs,
        Action(ActionKind.DISCARD, seat=0, tile=t7, declare_riichi=True),
    )
    assert out.new_state.table.kyoutaku == RIICHI_STICK_POINTS
    assert out.new_state.table.scores[0] == st.scores[0] - RIICHI_STICK_POINTS
    nb = out.new_state.board
    assert nb is not None
    assert nb.riichi[0] is True
    assert nb.river[-1].riichi is True
    assert 0 in nb.ippatsu_eligible
    assert 0 in nb.double_riichi


def test_riichi_insufficient_points() -> None:
    b, t7 = _board_chiitoitsu_dealer()
    st = initial_table_snapshot()
    low_scores = tuple(500 if i == 0 else 25000 for i in range(4))
    low = TableSnapshot(
        prevailing_wind=st.prevailing_wind,
        round_number=st.round_number,
        dealer_seat=st.dealer_seat,
        honba=st.honba,
        kyoutaku=st.kyoutaku,
        scores=low_scores,
        match_preset=st.match_preset,
    )
    gs = GameState(phase=GamePhase.IN_ROUND, table=low, board=b)
    with pytest.raises(IllegalActionError, match="insufficient"):
        apply(gs, Action(ActionKind.DISCARD, seat=0, tile=t7, declare_riichi=True))


def test_riichi_not_tenpai_rejected() -> None:
    b0 = _board(seed=1, dealer=0)
    t = next(iter(b0.hands[0].elements()))
    gs = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b0)
    with pytest.raises(IllegalActionError, match="tenpai"):
        apply(gs, Action(ActionKind.DISCARD, seat=0, tile=t, declare_riichi=True))


def test_after_riichi_must_tsumogiri_via_play_layer() -> None:
    """立直后仅允许摸切：用构造盘面直接测 ``apply_discard``。"""
    b, _t7 = _board_chiitoitsu_dealer()
    drawn = Tile(Suit.MAN, 1)
    nh = list(b.hands)
    assert nh[0][drawn] >= 1
    b = BoardState(
        hands=tuple(nh),
        live_wall=b.live_wall,
        live_draw_index=b.live_draw_index,
        dead_wall=b.dead_wall,
        revealed_indicators=b.revealed_indicators,
        current_seat=0,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b.river,
        melds=b.melds,
        last_draw_tile=drawn,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b.rinshan_draw_index,
        call_state=None,
        riichi=(True, False, False, False),
        ippatsu_eligible=frozenset(),
        double_riichi=frozenset(),
    )
    other = Tile(Suit.MAN, 2)
    with pytest.raises(ValueError, match="tsumogiri"):
        apply_discard(b, 0, other)


def test_shankuminkan_forbidden_when_riichi() -> None:
    from tests.test_kan import _board_with_pon_for_shankan

    b, quad_tile = _board_with_pon_for_shankan()
    d = b.current_seat
    ri = tuple(s == d for s in range(4))
    b = BoardState(
        hands=b.hands,
        live_wall=b.live_wall,
        live_draw_index=b.live_draw_index,
        dead_wall=b.dead_wall,
        revealed_indicators=b.revealed_indicators,
        current_seat=b.current_seat,
        turn_phase=b.turn_phase,
        river=b.river,
        melds=b.melds,
        last_draw_tile=b.last_draw_tile,
        last_draw_was_rinshan=b.last_draw_was_rinshan,
        rinshan_draw_index=b.rinshan_draw_index,
        call_state=b.call_state,
        riichi=ri,
        ippatsu_eligible=frozenset(),
        double_riichi=frozenset(),
    )
    ts = tuple(
        sorted(
            (quad_tile, quad_tile, quad_tile, quad_tile),
            key=lambda x: (x.rank, 1 if x.is_red else 0),
        )
    )
    sk = Meld(MeldKind.SHANKUMINKAN, ts, called_tile=quad_tile, from_seat=0)
    gs = GameState(phase=GamePhase.IN_ROUND, table=initial_table_snapshot(), board=b)
    with pytest.raises(IllegalActionError, match="riichi"):
        apply(gs, Action(ActionKind.SHANKUMINKAN, seat=d, meld=sk))


def test_board_after_ron_clears_ippatsu() -> None:
    from kernel.call.transitions import apply_ron, board_after_ron_winners

    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=42))
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    b = g1.board
    assert b is not None
    b = BoardState(
        hands=b.hands,
        live_wall=b.live_wall,
        live_draw_index=b.live_draw_index,
        dead_wall=b.dead_wall,
        revealed_indicators=b.revealed_indicators,
        current_seat=b.current_seat,
        turn_phase=b.turn_phase,
        river=b.river,
        melds=b.melds,
        last_draw_tile=b.last_draw_tile,
        last_draw_was_rinshan=b.last_draw_was_rinshan,
        rinshan_draw_index=b.rinshan_draw_index,
        call_state=b.call_state,
        riichi=b.riichi,
        ippatsu_eligible=frozenset({0, 1}),
        double_riichi=b.double_riichi,
    )
    ds = b.current_seat
    t0 = next(iter(b.hands[ds].elements()))
    b2 = apply_discard(b, ds, t0)
    cs = b2.call_state
    assert cs is not None
    s = next(iter(cs.ron_remaining))
    c13 = Counter(b2.hands[s])
    c13[cs.claimed_tile] -= 1
    if not is_tenpai_default(c13, b2.melds[s]):
        pytest.skip("该种子无上家可荣和听牌")
    b3 = apply_ron(b2, s)
    cs3 = b3.call_state
    assert cs3 is not None and cs3.finished
    settled = board_after_ron_winners(b3)
    assert settled.ippatsu_eligible == frozenset()
