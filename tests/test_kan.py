"""杠、岭上摸与杠宝指示牌。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    BoardState,
    IllegalActionError,
    Meld,
    MeldKind,
    RiverEntry,
    Suit,
    Tile,
    TurnPhase,
    apply,
    build_board_after_split,
    build_deck,
    shuffle_deck,
    split_wall,
)
from kernel.call.transitions import apply_open_meld, apply_ron
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.kan import (
    apply_after_kan_rinshan_draw,
    apply_ankan,
    apply_shankuminkan,
    completed_kan_rinshan_count,
)
from kernel.play import apply_discard
from kernel.play.model import CallResolution
from kernel.table import initial_table_snapshot
from tests.call_helpers import clear_call_window


def _board(*, seed: int = 0, dealer: int = 0) -> BoardState:
    w = tuple(shuffle_deck(build_deck(), seed=seed))
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def _find_dealer_quad_seed() -> tuple[BoardState, Tile]:
    for seed in range(800):
        b = _board(seed=seed, dealer=0)
        d = b.current_seat
        for t, n in b.hands[d].items():
            if n >= 4:
                return b, t
    msg = "no seed with dealer quad in range"
    raise RuntimeError(msg)


def _board_with_pon_for_shankan(*, seed: int = 7) -> tuple[BoardState, Tile]:
    """在四家手牌池内凑出：当前家 11 门内 + 1 张将用于加杠 + 已有 PON 三枚。"""
    b0 = _board(seed=seed, dealer=0)
    d = b0.current_seat
    merged = Counter()
    for h in b0.hands:
        merged.update(h)
    t = next(x for x, n in merged.items() if n >= 4)
    merged[t] -= 4
    hand0 = Counter({t: 1})
    r = merged.copy()
    for _ in range(10):
        x = next(iter(r.elements()))
        hand0[x] += 1
        r[x] -= 1
    assert sum(r.values()) == 39
    new_hands: list[Counter[Tile]] = []
    for s in range(4):
        if s == d:
            new_hands.append(hand0)
        else:
            take = Counter()
            for _ in range(13):
                x = next(iter(r.elements()))
                take[x] += 1
                r[x] -= 1
            new_hands.append(take)
    assert sum(r.values()) == 0
    ts = tuple(sorted((t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    pon = Meld(MeldKind.PON, ts, called_tile=t, from_seat=(d + 1) % 4)
    melds = tuple((pon,) if s == d else () for s in range(4))
    hands_t = tuple(new_hands)
    b = BoardState(
        hands=hands_t,
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=d,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b0.river,
        melds=melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=None,
    )
    return b, t


def test_after_kan_rinshan_advances_index_and_reveals_dora() -> None:
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    an = Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None)
    b1 = apply_ankan(b0, d, an)
    assert b1.rinshan_draw_index == b0.rinshan_draw_index + 1
    assert len(b1.revealed_indicators) == len(b0.revealed_indicators) + 1
    assert b1.last_draw_was_rinshan is True
    assert b1.last_draw_tile == b0.dead_wall.rinshan[b0.rinshan_draw_index]
    assert b1.revealed_indicators[-1] == b0.dead_wall.indicators[len(b0.revealed_indicators)]


def test_tile_conservation_136_through_ankan() -> None:
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    an = Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None)
    b1 = apply_ankan(b0, d, an)
    acc: Counter[Tile] = Counter()
    for h in b1.hands:
        acc.update(h)
    for s in range(4):
        for m in b1.melds[s]:
            acc.update(m.tiles)
    for e in b1.river:
        acc.update([e.tile])
    acc.update(b1.live_wall[b1.live_draw_index :])
    acc.update(b1.dead_wall.rinshan[b1.rinshan_draw_index :])
    acc.update(b1.dead_wall.ura_bases)
    acc.update(b1.dead_wall.indicators)
    assert acc == Counter(build_deck())


def test_no_more_dora_indicators_raises() -> None:
    """四枚表指示牌均已翻开后再杠，应拒绝翻下一张。"""
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    new_concealed = b0.hands[d].copy()
    for _ in range(4):
        new_concealed[quad] -= 1
    melds_l = list(b0.melds)
    melds_l[d] = b0.melds[d] + (
        Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None),
    )
    all_four = tuple(b0.dead_wall.indicators)
    intermediate = BoardState(
        hands=tuple(new_concealed if s == d else b0.hands[s] for s in range(4)),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=all_four,
        current_seat=d,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b0.river,
        melds=tuple(melds_l),
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=None,
    )
    with pytest.raises(ValueError, match="no more dora"):
        apply_after_kan_rinshan_draw(intermediate, d)


def test_shankuminkan_then_rinshan() -> None:
    b0, t = _board_with_pon_for_shankan()
    d = b0.current_seat
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    sk = Meld(MeldKind.SHANKUMINKAN, four, called_tile=None)
    b1 = apply_shankuminkan(b0, d, sk)
    assert b1.turn_phase == TurnPhase.CALL_RESPONSE
    assert b1.call_state is not None
    assert b1.call_state.chankan_rinshan_pending is True
    assert b1.rinshan_draw_index == b0.rinshan_draw_index
    b2 = clear_call_window(b1)
    assert b2.rinshan_draw_index == b0.rinshan_draw_index + 1
    assert b2.last_draw_was_rinshan is True
    assert any(m.kind == MeldKind.SHANKUMINKAN for m in b2.melds[d])


def _seven_pairs_tenpai_13(t: Tile) -> Counter[Tile]:
    """门清七对听：6 对与单骑 ``t``（``t`` 为数牌）。"""
    assert t.suit != Suit.HONOR
    ranks = [r for r in range(1, 10) if r != t.rank][:6]
    assert len(ranks) == 6
    c: Counter[Tile] = Counter()
    for r in ranks:
        tt = Tile(t.suit, r, False)
        c[tt] = 2
    c[t] = 1
    return c


def test_chankan_ron_after_shankuminkan() -> None:
    b0, t = _board_with_pon_for_shankan()
    d = b0.current_seat
    opp = (d + 1) % 4
    donor = (d + 2) % 4
    old_opp = Counter(b0.hands[opp])
    h_new = _seven_pairs_tenpai_13(t)
    new_donor = Counter(b0.hands[donor])
    for tile, n in h_new.items():
        new_donor[tile] -= n
        if new_donor[tile] < 0:
            pytest.skip("对家牌型无法从 donor 置换出七对听")
    for tile, n in old_opp.items():
        new_donor[tile] += n
    rest_hands = [Counter(b0.hands[s]) for s in range(4)]
    rest_hands[opp] = h_new
    rest_hands[donor] = new_donor
    b_adj = BoardState(
        hands=tuple(rest_hands),
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=b0.current_seat,
        turn_phase=b0.turn_phase,
        river=b0.river,
        melds=b0.melds,
        last_draw_tile=b0.last_draw_tile,
        last_draw_was_rinshan=b0.last_draw_was_rinshan,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=b0.call_state,
    )
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    sk = Meld(MeldKind.SHANKUMINKAN, four, called_tile=None)
    b1 = apply_shankuminkan(b_adj, d, sk)
    b2 = apply_ron(b1, opp)
    assert opp in b2.call_state.ron_claimants
    assert b2.call_state.finished is True


def test_chankan_rejects_open_meld() -> None:
    b0, t = _board_with_pon_for_shankan()
    d = b0.current_seat
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    sk = Meld(MeldKind.SHANKUMINKAN, four, called_tile=None)
    b1 = apply_shankuminkan(b0, d, sk)
    if t.suit == Suit.HONOR or not (2 <= t.rank <= 8):
        pytest.skip("需中间数牌才能构造吃")
    t_lo = Tile(t.suit, t.rank - 1, False)
    t_hi = Tile(t.suit, t.rank + 1, False)
    chi = Meld(MeldKind.CHI, (t_lo, t, t_hi), called_tile=t)
    with pytest.raises(ValueError, match="抢杠"):
        apply_open_meld(b1, (d + 3) % 4, chi)


def test_engine_ankan_and_discard_clears_rinshan_flag() -> None:
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    g0 = GameState(
        phase=GamePhase.IN_ROUND,
        table=initial_table_snapshot(dealer_seat=0),
        board=b0,
        ron_winners=None,
    )
    an = Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None)
    g1 = apply(g0, Action(ActionKind.ANKAN, seat=d, meld=an)).new_state
    b1 = g1.board
    assert b1 is not None
    assert b1.last_draw_was_rinshan is True
    t_drop = next(iter(b1.hands[d].elements()))
    g2 = apply(g1, Action(ActionKind.DISCARD, seat=d, tile=t_drop)).new_state
    b2 = g2.board
    assert b2 is not None
    assert b2.last_draw_was_rinshan is False


def test_engine_ankan_rejected_in_need_draw() -> None:
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    t0 = next(t for t in b0.hands[d].elements() if t != quad)
    b1 = apply_discard(b0, d, t0)
    b1 = clear_call_window(b1)
    assert b1.turn_phase == TurnPhase.NEED_DRAW
    g0 = GameState(
        phase=GamePhase.IN_ROUND,
        table=initial_table_snapshot(dealer_seat=0),
        board=b1,
        ron_winners=None,
    )
    an = Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None)
    with pytest.raises(IllegalActionError, match="MUST_DISCARD"):
        apply(g0, Action(ActionKind.ANKAN, seat=d, meld=an))


def _seed_with_at_least_four_of(tile: Tile) -> int:
    for seed in range(500):
        b = _board(seed=seed, dealer=0)
        m = Counter()
        for h in b.hands:
            m.update(h)
        if m[tile] >= 4:
            return seed
    msg = "no seed with four copies of tile in dealt hands"
    raise RuntimeError(msg)


def _board_call_response_daiminkan_ready() -> tuple[BoardState, Tile]:
    """``CALL_RESPONSE`` / ``pon_kan``：席 0 已打出 ``T``，席 1 可大明杠。"""
    t = Tile(Suit.MAN, 1, False)
    seed = _seed_with_at_least_four_of(t)
    b0 = _board(seed=seed, dealer=0)
    ds = 0
    merged = Counter()
    for h in b0.hands:
        merged.update(h)
    assert merged[t] >= 4
    merged[t] -= 4
    rest = merged.copy()
    h1 = Counter({t: 3})
    for _ in range(10):
        x = next(iter(rest.elements()))
        h1[x] += 1
        rest[x] -= 1
    h0 = Counter()
    h2 = Counter()
    h3 = Counter()
    for target in (h0, h2, h3):
        for _ in range(13):
            x = next(iter(rest.elements()))
            target[x] += 1
            rest[x] -= 1
    assert sum(rest.values()) == 0
    assert h0[t] == 0
    hands = (h0, h1, h2, h3)
    river = (RiverEntry(seat=ds, tile=t, tsumogiri=False),)
    cs = CallResolution(
        discard_seat=ds,
        claimed_tile=t,
        river_index=0,
        stage="pon_kan",
        ron_remaining=frozenset(),
        ron_claimants=frozenset(),
        pon_kan_order=(1, 2, 3),
        pon_kan_idx=0,
        finished=False,
    )
    return (
        BoardState(
            hands=hands,
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=1,
            turn_phase=TurnPhase.CALL_RESPONSE,
            river=river,
            melds=((), (), (), ()),
            last_draw_tile=None,
            last_draw_was_rinshan=False,
            rinshan_draw_index=0,
            call_state=cs,
        ),
        t,
    )


def test_daiminkan_open_meld_triggers_rinshan() -> None:
    b, t = _board_call_response_daiminkan_ready()
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    meld = Meld(MeldKind.DAIMINKAN, four, called_tile=t)
    b2 = apply_open_meld(b, 1, meld)
    assert b2.rinshan_draw_index == 1
    assert b2.last_draw_was_rinshan is True
    assert b2.last_draw_tile == b.dead_wall.rinshan[0]
    assert len(b2.revealed_indicators) == len(b.revealed_indicators) + 1
    assert completed_kan_rinshan_count(b2) == 1


def test_completed_kan_rinshan_count_matches_index() -> None:
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    an = Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None)
    b1 = apply_ankan(b0, d, an)
    assert completed_kan_rinshan_count(b1) == b1.rinshan_draw_index == 1
