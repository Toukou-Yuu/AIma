"""点数公式、荣和结算与振听。"""

from __future__ import annotations

from collections import Counter

from kernel import BoardState, Tile, build_board_after_split, build_deck, split_wall
from kernel.board import BoardState as BS
from kernel.board import CallResolution, RiverEntry, TurnPhase
from kernel.scoring.dora import ura_indicators_for_settlement
from kernel.scoring.furiten import is_furiten_for_tile
from kernel.scoring.points import (
    child_ron_base_points,
    child_ron_payment_from_discarder,
    round_up_100,
)
from kernel.scoring.settle import settle_ron_table
from kernel.table.model import initial_table_snapshot
from kernel.tiles.model import Suit


def _board_sorted_deal(*, dealer: int = 0) -> BoardState:
    """未洗牌牌山，测试用砌牌可复现。"""
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def _pool_not_in_wall(b0: BoardState) -> Counter[Tile]:
    """136 −（本墙未摸段 + 王牌岭上 + 指示牌槽）= 已配手牌与河可占用的 53 张。"""
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


def _chiitoitsu_ron_board() -> BS:
    """seat1 七对听 7m；seat0 河底打 7m；``CALL_RESPONSE`` 且荣和阶段已结束。

    对子跨万／筒，避免全万清一色与七对子叠番导致打点与旧断言不一致。
    """
    b0 = _board_sorted_deal(dealer=0)
    pool = _pool_not_in_wall(b0)
    t7 = Tile(Suit.MAN, 7)
    assert pool[t7] >= 2
    hand1 = Counter()
    for r in range(1, 6):
        t = Tile(Suit.MAN, r)
        for _ in range(2):
            assert pool[t] >= 1
            pool[t] -= 1
            if pool[t] == 0:
                del pool[t]
            hand1[t] += 1
    t1p = Tile(Suit.PIN, 1)
    for _ in range(2):
        assert pool[t1p] >= 1
        pool[t1p] -= 1
        if pool[t1p] == 0:
            del pool[t1p]
        hand1[t1p] += 1
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
            continue
        new_hands.append(_take_n(pool, 13))
    assert sum(pool.values()) == 0
    river = (RiverEntry(0, t7),)
    cs = CallResolution(
        discard_seat=0,
        claimed_tile=t7,
        river_index=0,
        stage="ron",
        ron_remaining=frozenset(),
        ron_claimants=frozenset({1}),
        pon_kan_order=(1, 2, 3),
        pon_kan_idx=0,
        finished=True,
    )
    return BS(
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


def test_ura_indicators_for_settlement_matches_revealed_count() -> None:
    b0 = _board_sorted_deal()
    dead = b0.dead_wall
    assert ura_indicators_for_settlement(dead, 0) == ()
    assert ura_indicators_for_settlement(dead, 1) == (dead.ura_bases[0],)
    assert len(ura_indicators_for_settlement(dead, len(b0.revealed_indicators))) == len(
        b0.revealed_indicators
    )


def test_round_up_100() -> None:
    assert round_up_100(2500) == 2500
    assert round_up_100(2501) == 2600


def test_child_ron_payment_mangan_floor() -> None:
    p = child_ron_payment_from_discarder(
        winner=1,
        discarder=0,
        dealer=2,
        fu=30,
        han=5,
        honba=0,
    )
    assert p == 8_000


def test_settle_ron_chiitoitsu_transfers_scores() -> None:
    b = _chiitoitsu_ron_board()
    tab = initial_table_snapshot()
    # 七对子：25 符 2 番
    pay = child_ron_payment_from_discarder(
        1,
        0,
        tab.dealer_seat,
        25,
        2,
        tab.honba,
    )
    ura = ura_indicators_for_settlement(b.dead_wall, len(b.revealed_indicators))
    new_tab, _, _ = settle_ron_table(
        tab,
        b,
        ron_winners=frozenset({1}),
        discard_seat=0,
        win_tile=Tile(Suit.MAN, 7),
        ura_indicators=ura,
    )
    assert new_tab.scores[0] == tab.scores[0] - pay
    assert new_tab.scores[1] == tab.scores[1] + pay


def test_settle_ron_kyoutaku_to_winner() -> None:
    b = _chiitoitsu_ron_board()
    tab = initial_table_snapshot(kyoutaku=1001)
    # 七对子：25 符 2 番
    pay = child_ron_payment_from_discarder(
        1,
        0,
        tab.dealer_seat,
        25,
        2,
        tab.honba,
    )
    ura = ura_indicators_for_settlement(b.dead_wall, len(b.revealed_indicators))
    new_tab, _, _ = settle_ron_table(
        tab,
        b,
        ron_winners=frozenset({1}),
        discard_seat=0,
        win_tile=Tile(Suit.MAN, 7),
        ura_indicators=ura,
    )
    assert new_tab.kyoutaku == 0
    assert new_tab.scores[1] == tab.scores[1] + pay + 1001
    assert new_tab.scores[0] == tab.scores[0] - pay


def _board_need_draw_with_river(seat_disc: int, tile: Tile) -> BS:
    """合法 ``NEED_DRAW``：河中仅一枚该席舍牌（用于振听判定单测）。"""
    b0 = _board_sorted_deal(dealer=0)
    pool = _pool_not_in_wall(b0)
    assert pool[tile] >= 1
    pool[tile] -= 1
    if pool[tile] == 0:
        del pool[tile]
    new_hands = tuple(_take_n(pool, 13) for _ in range(4))
    assert sum(pool.values()) == 0
    river = (RiverEntry(seat_disc, tile),)
    return BS(
        hands=new_hands,
        live_wall=b0.live_wall,
        live_draw_index=b0.live_draw_index,
        dead_wall=b0.dead_wall,
        revealed_indicators=b0.revealed_indicators,
        current_seat=b0.current_seat,
        turn_phase=TurnPhase.NEED_DRAW,
        river=river,
        melds=b0.melds,
        last_draw_tile=None,
        last_draw_was_rinshan=False,
        rinshan_draw_index=b0.rinshan_draw_index,
        call_state=None,
    )


def test_is_furiten_when_own_river_contains_win_tile() -> None:
    t5 = Tile(Suit.MAN, 5)
    b = _board_need_draw_with_river(2, t5)
    assert is_furiten_for_tile(b, 2, t5) is True
    assert is_furiten_for_tile(b, 1, t5) is False


class TestRiichiFuriten:
    """M5: 立直后振听应检查所有听牌，而非仅当前和了牌。"""

    def test_riichi_furiten_different_waiting_tile_in_river(self) -> None:
        """M5: 立直双碰听牌，河中有听牌 A，检查听牌 B 也应振听。"""
        b0 = _board_sorted_deal()
        pool = _pool_not_in_wall(b0)
        # 手牌：1m1m1m 2m2m2m 3m3m3m 4m4m 5m5m（13 张，双碰听 4m 或 5m）
        hand_tiles = [
            Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1),
            Tile(Suit.MAN, 2), Tile(Suit.MAN, 2), Tile(Suit.MAN, 2),
            Tile(Suit.MAN, 3), Tile(Suit.MAN, 3), Tile(Suit.MAN, 3),
            Tile(Suit.MAN, 4), Tile(Suit.MAN, 4),
            Tile(Suit.MAN, 5), Tile(Suit.MAN, 5),
        ]
        hand = Counter(hand_tiles)
        for t, n in hand.items():
            pool[t] -= n
            if pool[t] == 0:
                del pool[t]
        hands = [hand]
        for _ in range(2):
            hands.append(_take_n(pool, 13))
        hands.append(Counter(pool.elements()))

        # 河中有 4m（听牌之一），检查 5m 是否振听
        t4m = Tile(Suit.MAN, 4)
        t5m = Tile(Suit.MAN, 5)
        river = (RiverEntry(0, t4m),)
        b = _mock_board(
            b0,
            hands=tuple(hands),
            river=river,
            riichi=(True, False, False, False),
            current_seat=0,
            turn_phase=TurnPhase.NEED_DRAW,
        )
        # 河中有 4m，检查 5m：立直振听应该返回 True
        assert is_furiten_for_tile(b, 0, t5m) is True

    def test_non_riichi_not_furiten_for_different_tile(self) -> None:
        """非立直时只检查当前和了牌。"""
        t5 = Tile(Suit.MAN, 5)
        t3 = Tile(Suit.MAN, 3)
        b = _board_need_draw_with_river(2, t5)
        # 河中有 5m，检查 3m → 不振听（非立直只检查具体牌）
        assert is_furiten_for_tile(b, 2, t3) is False

    def test_riichi_no_furiten_when_no_waiting_in_river(self) -> None:
        """立直但听牌不在河中 → 不振听。"""
        b0 = _board_sorted_deal()
        pool = _pool_not_in_wall(b0)
        # 手牌：1m1m1m 2m2m2m 3m3m3m 4m4m 5m5m（13 张，双碰听 4m 或 5m）
        hand_tiles = [
            Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1),
            Tile(Suit.MAN, 2), Tile(Suit.MAN, 2), Tile(Suit.MAN, 2),
            Tile(Suit.MAN, 3), Tile(Suit.MAN, 3), Tile(Suit.MAN, 3),
            Tile(Suit.MAN, 4), Tile(Suit.MAN, 4),
            Tile(Suit.MAN, 5), Tile(Suit.MAN, 5),
        ]
        hand = Counter(hand_tiles)
        for t, n in hand.items():
            pool[t] -= n
            if pool[t] == 0:
                del pool[t]
        hands = [hand]
        for _ in range(2):
            hands.append(_take_n(pool, 13))
        hands.append(Counter(pool.elements()))

        # 河中没有听牌（打了一张无关牌）
        t1p = Tile(Suit.PIN, 1)
        river = (RiverEntry(0, t1p),)
        b = _mock_board(
            b0,
            hands=tuple(hands),
            river=river,
            riichi=(True, False, False, False),
            current_seat=0,
            turn_phase=TurnPhase.NEED_DRAW,
        )
        t4m = Tile(Suit.MAN, 4)
        assert is_furiten_for_tile(b, 0, t4m) is False


# --- M3: _is_hotei ---

def _mock_board(b0: BoardState, **overrides) -> BoardState:
    """绕过 __post_init__ 验证构造修改后的 BoardState。"""
    import dataclasses as dc

    b = object.__new__(BoardState)
    for f in dc.fields(b0):
        val = overrides.get(f.name, getattr(b0, f.name))
        object.__setattr__(b, f.name, val)
    return b


class TestHotei:
    """M3: 河底捞鱼应使用本墙耗尽判定，而非 river_count >= 17 近似。"""

    def test_hotei_wall_exhausted(self) -> None:
        """本墙已空 → 河底 = True。"""
        from kernel.scoring.settle import _is_hotei

        b0 = _board_sorted_deal()
        b = _mock_board(b0, live_draw_index=len(b0.live_wall))
        assert _is_hotei(b, discard_seat=0) is True

    def test_hotei_wall_not_exhausted(self) -> None:
        """本墙未空 → 河底 = False。"""
        from kernel.scoring.settle import _is_hotei

        b0 = _board_sorted_deal()
        assert _is_hotei(b0, discard_seat=0) is False

    def test_hotei_with_melds_wall_exhausted(self) -> None:
        """有副露时 river_count 远少 17，但本墙已空仍为河底。"""
        from kernel.scoring.settle import _is_hotei

        b0 = _board_sorted_deal()
        river = tuple(RiverEntry(0, b0.hands[0].most_common(1)[0][0]) for _ in range(3))
        b = _mock_board(b0, live_draw_index=len(b0.live_wall), river=river)
        assert _is_hotei(b, discard_seat=0) is True


class TestKiriageMangan:
    """切上满贯测试。"""

    def test_kiriage_mangan_3han_110fu(self) -> None:
        """3 番 110 符：切上满贯 8000 点。"""
        # 110 符：罕见情况（例：字一色副露 + 单骑 + 役牌）
        base = child_ron_base_points(fu=110, han=3)
        assert base == 8_000  # 切上满贯

    def test_mangan_cap_4han_70fu(self) -> None:
        """4 番 70 符：满贯封顶 8000 点。"""
        base = child_ron_base_points(fu=70, han=4)
        assert base == 8_000

    def test_mangan_cap_3han_100fu(self) -> None:
        """3 番 100 符：满贯封顶 8000 点。"""
        base = child_ron_base_points(fu=100, han=3)
        assert base == 8000

    def test_mangan_cap_4han_60fu(self) -> None:
        """4 番 60 符：满贯封顶 8000 点。"""
        base = child_ron_base_points(fu=60, han=4)
        assert base == 8000
