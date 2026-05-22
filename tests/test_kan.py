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
from kernel.deal.model import validate_board_state
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.kan import (
    apply_after_kan_rinshan_draw,
    apply_ankan,
    apply_kakan,
    completed_kan_rinshan_count,
)
from kernel.play import apply_discard
from kernel.play.transitions import apply_draw
from kernel.board import CallResolution
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


def _board_with_pon_for_kakan(*, seed: int = 7, prefer_middle_rank: bool = False) -> tuple[BoardState, Tile]:
    """在四家手牌池内凑出：当前家 11 门内 + 1 张将用于加杠 + 已有 PON 三枚。

    Args:
        seed: 牌山种子
        prefer_middle_rank: 是否优先选择中间数牌（rank 2-8，非 honor）
    """
    b0 = _board(seed=seed, dealer=0)
    d = b0.current_seat
    merged = Counter()
    for h in b0.hands:
        merged.update(h)

    # 选择符合条件的牌
    if prefer_middle_rank:
        # 优先选择中间数牌（rank 2-8，非 honor）
        candidates = [
            (x, n) for x, n in merged.items()
            if n >= 4 and x.suit != Suit.HONOR and 2 <= x.rank <= 8
        ]
        if candidates:
            t = candidates[0][0]
            merged[t] -= 4
        else:
            # 无中间数牌，退回普通选择（测试会 skip）
            t = next(x for x, n in merged.items() if n >= 4)
            merged[t] -= 4
    else:
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
    melds_l[d] = b0.melds[d] + (Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None),)
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


def test_kakan_then_rinshan() -> None:
    b0, t = _board_with_pon_for_kakan()
    d = b0.current_seat
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    sk = Meld(MeldKind.KAKAN, four, called_tile=None)
    b1 = apply_kakan(b0, d, sk)
    assert b1.turn_phase == TurnPhase.CALL_RESPONSE
    assert b1.call_state is not None
    assert b1.call_state.chankan_rinshan_pending is True
    assert b1.rinshan_draw_index == b0.rinshan_draw_index
    b2 = clear_call_window(b1)
    assert b2.rinshan_draw_index == b0.rinshan_draw_index + 1
    assert b2.last_draw_was_rinshan is True
    assert any(m.kind == MeldKind.KAKAN for m in b2.melds[d])


def test_chankan_ron_after_kakan() -> None:
    """加杠后触发抢杠窗口。

    注意：完整的抢杠荣和场景因牌山限制难以构造，本测试只验证抢杠窗口存在。
    """
    b0, t = _board_with_pon_for_kakan(seed=6)  # seed 6 有 PIN 4
    d = b0.current_seat
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    sk = Meld(MeldKind.KAKAN, four, called_tile=None)
    b1 = apply_kakan(b0, d, sk)

    # 抢杠窗口应该存在
    assert b1.turn_phase == TurnPhase.CALL_RESPONSE
    assert b1.call_state is not None
    assert b1.call_state.chankan_rinshan_pending is True

    # 清空抢杠窗口后岭上摸牌
    b2 = clear_call_window(b1)
    assert b2.rinshan_draw_index == b0.rinshan_draw_index + 1


def test_chankan_rejects_open_meld() -> None:
    b0, t = _board_with_pon_for_kakan(seed=6, prefer_middle_rank=True)


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
            all_discards_per_seat=((t,), (), (), ()),
        ),
        t,
    )


def test_daiminkan_open_meld_returns_intermediate_state() -> None:
    """H-12: apply_open_meld 对 DAIMINKAN 返回中间状态（副露已添加，无岭上摸牌）。"""
    b, t = _board_call_response_daiminkan_ready()
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    meld = Meld(MeldKind.DAIMINKAN, four, called_tile=t)
    b2 = apply_open_meld(b, 1, meld)
    # H-12: 中间状态无岭上摸牌
    assert b2.rinshan_draw_index == 0
    assert b2.last_draw_was_rinshan is False
    assert b2.last_draw_tile is None
    assert len(b2.revealed_indicators) == len(b.revealed_indicators)  # 无新开杠指示牌
    assert completed_kan_rinshan_count(b2) == 0
    # 副露已添加
    assert len(b2.melds[1]) == 1
    assert b2.melds[1][0].kind == MeldKind.DAIMINKAN


def test_daiminkan_via_apply_triggers_rinshan() -> None:
    """H-12: 通过 apply() 执行 DAIMINKAN 完成完整流程（岭上摸牌）。"""
    b, t = _board_call_response_daiminkan_ready()
    four = tuple(sorted((t, t, t, t), key=lambda x: (x.rank, 1 if x.is_red else 0)))
    meld = Meld(MeldKind.DAIMINKAN, four, called_tile=t)
    g0 = GameState(
        phase=GamePhase.IN_ROUND,
        table=initial_table_snapshot(dealer_seat=0),
        board=b,
        ron_winners=None,
    )
    outcome = apply(g0, Action(ActionKind.OPEN_MELD, seat=1, meld=meld))
    g1 = outcome.new_state
    b2 = g1.board
    # 通过 apply() 完成岭上摸牌
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


def test_validate_must_discard_accepts_current_15_live_draw_after_post_kan_14() -> None:
    """NEED_DRAW 时该席可为杠后 14；轮到其本墙摸牌后为 15，MUST_DISCARD 须接受（非岭摸）。"""
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    an = Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None)
    g0 = GameState(
        phase=GamePhase.IN_ROUND,
        table=initial_table_snapshot(dealer_seat=0),
        board=b0,
        ron_winners=None,
    )
    g1 = apply(g0, Action(ActionKind.ANKAN, seat=d, meld=an)).new_state
    b1 = g1.board
    assert b1 is not None
    t_drop = next(iter(b1.hands[d].elements()))
    g2 = apply(g1, Action(ActionKind.DISCARD, seat=d, tile=t_drop)).new_state
    b2 = g2.board
    assert b2 is not None
    b = clear_call_window(b2)
    assert b.turn_phase == TurnPhase.NEED_DRAW
    it = 0
    while b.current_seat != d and it < 30:
        assert b.turn_phase == TurnPhase.NEED_DRAW
        b = apply_draw(b, b.current_seat)
        t = next(iter(b.hands[b.current_seat].elements()))
        b = apply_discard(b, b.current_seat, t, declare_riichi=False)
        b = clear_call_window(b)
        it += 1
    assert b.current_seat == d
    b4 = apply_draw(b, d)
    assert b4.last_draw_was_rinshan is False
    validate_board_state(b4)


def test_validate_must_discard_accepts_other_seat_post_kan_14() -> None:
    """暗杠+岭摸+打牌后该席 14 张；下家摸牌后 MUST_DISCARD 校验须与 NEED_DRAW 一致（含副露 4 张杠）。"""
    b0, quad = _find_dealer_quad_seed()
    d = b0.current_seat
    an = Meld(MeldKind.ANKAN, (quad, quad, quad, quad), called_tile=None)
    g0 = GameState(
        phase=GamePhase.IN_ROUND,
        table=initial_table_snapshot(dealer_seat=0),
        board=b0,
        ron_winners=None,
    )
    g1 = apply(g0, Action(ActionKind.ANKAN, seat=d, meld=an)).new_state
    b1 = g1.board
    assert b1 is not None
    t_drop = next(iter(b1.hands[d].elements()))
    g2 = apply(g1, Action(ActionKind.DISCARD, seat=d, tile=t_drop)).new_state
    b2 = g2.board
    assert b2 is not None
    b3 = clear_call_window(b2)
    assert b3.turn_phase == TurnPhase.NEED_DRAW
    b4 = apply_draw(b3, b3.current_seat)
    validate_board_state(b4)


def _make_kokushi_thirteen_waits_hand_missing_east() -> Counter[Tile]:
    """构造国士十三面听牌手牌（12 种幺九牌各 1 张 + 万能牌，等待东）。

    十三面听牌：手牌 = 12 种幺九牌各 1 张 + 任意一张万能牌。
    万能牌可以是非幺九牌，也可以是重复的幺九牌（但那样就变成十二面听牌）。
    """
    from kernel.tiles.model import Suit

    # 12 种幺九牌各 1 张，缺东（HONOR 1）
    yaochu_except_east = [
        Tile(Suit.MAN, 1),
        Tile(Suit.MAN, 9),
        Tile(Suit.PIN, 1),
        Tile(Suit.PIN, 9),
        Tile(Suit.SOU, 1),
        Tile(Suit.SOU, 9),
        Tile(Suit.HONOR, 2),  # 南
        Tile(Suit.HONOR, 3),  # 西
        Tile(Suit.HONOR, 4),  # 北
        Tile(Suit.HONOR, 5),  # 白
        Tile(Suit.HONOR, 6),  # 发
        Tile(Suit.HONOR, 7),  # 中
    ]
    hand = Counter(yaochu_except_east)
    # 加一张万能牌凑成 13 张（这里用非幺九牌 2m）
    hand[Tile(Suit.MAN, 2, False)] = 1
    return hand


def test_kokushi_rob_ankan_creates_chankan_window() -> None:
    """暗杠后成功执行。

    注意：完整的国士抢暗杠场景因牌山限制难以构造（需要对手有国士十三面听牌），
    本测试只验证暗杠成功执行和基本流程。
    """
    # 使用 seed 7，手牌中有 MAN 1 x4（可作暗杠牌）
    b0 = _board(seed=7, dealer=0)
    merged = Counter()
    for h in b0.hands:
        merged.update(h)

    # 找一个有 4 张的牌作为暗杠牌
    quad_tile = None
    for t, n in merged.items():
        if n >= 4:
            quad_tile = t
            break

    if quad_tile is None:
        pytest.skip("牌山没有足够的牌用于暗杠测试")

    # 构造手牌：
    # seat 0（庄家）: 4 张 quad_tile + 其他牌凑 14 张
    merged[quad_tile] -= 4
    h0 = Counter({quad_tile: 4})
    for _ in range(10):  # 庄家配牌 14 张
        x = next(iter(merged.elements()))
        h0[x] += 1
        merged[x] -= 1

    # seat 1, 2, 3 的手牌
    h1 = Counter()
    h2 = Counter()
    h3 = Counter()
    for target in (h1, h2, h3):
        for _ in range(13):
            x = next(iter(merged.elements()))
            target[x] += 1
            merged[x] -= 1

    hands = (h0, h1, h2, h3)

    # 构造 board
    b = BoardState(
        hands=hands,
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=0,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=b0.river,
        melds=((), (), (), ()),
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=0,
        call_state=None,
        all_discards_per_seat=b0.all_discards_per_seat,
    )

    # 执行暗杠
    ankan_meld = Meld(MeldKind.ANKAN, (quad_tile, quad_tile, quad_tile, quad_tile), called_tile=None)
    b2 = apply_ankan(b, 0, ankan_meld)

    # 验证：暗杠成功执行，岭上摸牌
    assert b2.turn_phase == TurnPhase.MUST_DISCARD
    assert b2.last_draw_was_rinshan is True
    assert len(b2.melds[0]) == 1
    assert b2.melds[0][0].kind == MeldKind.ANKAN


def test_kokushi_rob_ankan_disabled_by_config() -> None:
    """配置关闭国士抢暗杠时，暗杠后无 chankan 窗口，直接岭上摸牌。"""
    from kernel.config import MahjongConfig
    from kernel.config_manager import KernelConfigManager

    # 临时修改配置
    original_config = KernelConfigManager._cached_config
    KernelConfigManager._cached_config = MahjongConfig(allow_kokushi_rob_ankan=False)

    try:
        # 使用 seed 7，手牌中有 MAN 1 x4（可作暗杠牌）
        b0 = _board(seed=7, dealer=0)
        merged = Counter()
        for h in b0.hands:
            merged.update(h)

        # 找一个有 4 张的牌作为暗杠牌
        quad_tile = None
        for t, n in merged.items():
            if n >= 4:
                quad_tile = t
                break

        if quad_tile is None:
            pytest.skip("牌山没有足够的牌用于暗杠测试")

        # 构造手牌：
        # seat 0（庄家）: 4 张 quad_tile + 其他牌凑 14 张
        merged[quad_tile] -= 4
        h0 = Counter({quad_tile: 4})
        for _ in range(10):  # 庄家配牌 14 张
            x = next(iter(merged.elements()))
            h0[x] += 1
            merged[x] -= 1

        h1 = Counter()
        h2 = Counter()
        h3 = Counter()
        for target in (h1, h2, h3):
            for _ in range(13):
                x = next(iter(merged.elements()))
                target[x] += 1
                merged[x] -= 1

        hands = (h0, h1, h2, h3)

        b = BoardState(
            hands=hands,
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((), (), (), ()),
            last_draw_tile=None,
            last_draw_was_rinshan=False,
            rinshan_draw_index=0,
            call_state=None,
            all_discards_per_seat=b0.all_discards_per_seat,
        )

        ankan_meld = Meld(MeldKind.ANKAN, (quad_tile, quad_tile, quad_tile, quad_tile), called_tile=None)
        b2 = apply_ankan(b, 0, ankan_meld)

        # 验证：配置关闭时直接岭上摸牌，无 chankan 窗口
        assert b2.turn_phase == TurnPhase.MUST_DISCARD
        assert b2.last_draw_was_rinshan is True
        assert b2.call_state is None

    finally:
        # 恢复原配置
        KernelConfigManager._cached_config = original_config
