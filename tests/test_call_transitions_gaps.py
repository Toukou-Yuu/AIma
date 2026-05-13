"""call.transitions 覆盖缺口测试：chi/pon/daiminkan/ron 路径。"""

from __future__ import annotations

from collections import Counter

from kernel import Tile, Suit
from kernel.call.win import can_ron_default
from kernel.deal.model import BoardState
from kernel.hand.melds import Meld, MeldKind
from kernel.play.model import CallResolution, RiverEntry, TurnPhase
from kernel.play.transitions import apply_discard, apply_draw

from tests.engine_helpers import (
    board_sorted_deal,
    make_board,
    make_board_with_discard,
    make_meld,
    pool_not_in_wall,
    take_n,
)
from tests.call_helpers import clear_call_window

# --- 牌常量 ---
MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN4 = Tile(Suit.MAN, 4)
MAN5 = Tile(Suit.MAN, 5)
MAN6 = Tile(Suit.MAN, 6)
MAN7 = Tile(Suit.MAN, 7)
MAN8 = Tile(Suit.MAN, 8)
MAN9 = Tile(Suit.MAN, 9)
PIN1 = Tile(Suit.PIN, 1)
PIN2 = Tile(Suit.PIN, 2)
PIN3 = Tile(Suit.PIN, 3)
PIN4 = Tile(Suit.PIN, 4)
PIN5 = Tile(Suit.PIN, 5)
PIN6 = Tile(Suit.PIN, 6)
PIN7 = Tile(Suit.PIN, 7)
PIN8 = Tile(Suit.PIN, 8)
PIN9 = Tile(Suit.PIN, 9)
SOU1 = Tile(Suit.SOU, 1)
SOU2 = Tile(Suit.SOU, 2)
SOU3 = Tile(Suit.SOU, 3)
SOU4 = Tile(Suit.SOU, 4)
SOU5 = Tile(Suit.SOU, 5)
SOU6 = Tile(Suit.SOU, 6)
SOU7 = Tile(Suit.SOU, 7)
SOU8 = Tile(Suit.SOU, 8)
SOU9 = Tile(Suit.SOU, 9)
HAKU = Tile(Suit.HONOR, 5)
HATSU = Tile(Suit.HONOR, 6)
CHUN = Tile(Suit.HONOR, 7)
TON = Tile(Suit.HONOR, 1)
NAN = Tile(Suit.HONOR, 2)


# --- 吃（chi）测试 ---

class TestChiClaim:
    """吃牌路径覆盖。"""

    def test_chi_window_state(self) -> None:
        """构造 chi 应答窗口状态。"""
        # seat0 打出 4m，seat1 有 3m5m 可以吃
        b0 = board_sorted_deal(dealer=0)
        pool = pool_not_in_wall(b0)
        # seat1: 3m5m + 11 张其他
        hand1 = Counter({MAN3: 1, MAN5: 1})
        pool[MAN3] -= 1
        pool[MAN5] -= 1
        for t in [MAN3, MAN5]:
            if pool[t] == 0:
                del pool[t]
        hand1.update(take_n(pool, 11))
        # seat0: 含 4m 的 14 张
        hand0 = take_n(pool, 13)
        hand0[MAN4] += 1
        pool[MAN4] -= 1
        if pool[MAN4] == 0:
            del pool[MAN4]
        hand2 = take_n(pool, 13)
        hand3 = take_n(pool, 13)

        b = BoardState(
            hands=(hand0, hand1, hand2, hand3),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=(),
            melds=b0.melds,
            last_draw_tile=None,
            last_draw_was_rinshan=False,
            rinshan_draw_index=0,
            call_state=None,
            riichi=(False, False, False, False),
            ippatsu_eligible=frozenset(),
            double_riichi=frozenset(),
            all_discards_per_seat=((), (), (), ()),
            called_discard_indices=(frozenset(), frozenset(), frozenset(), frozenset()),
        )

        # seat0 打出 4m
        b1 = apply_discard(b, 0, MAN4)
        assert b1.turn_phase == TurnPhase.CALL_RESPONSE
        assert b1.call_state is not None
        assert b1.call_state.discard_seat == 0

        # seat1 有 3m5m，可以吃 4m 形成 3m4m5m
        assert MAN3 in b1.hands[1] and MAN5 in b1.hands[1]


# --- 碰（pon）测试 ---

class TestPonClaim:
    """碰牌路径覆盖。"""

    def test_pon_window_state(self) -> None:
        """构造碰应答窗口状态。"""
        # seat0 打出 5m，seat1 有两张 5m 可以碰
        b0 = board_sorted_deal(dealer=0)
        pool = pool_not_in_wall(b0)
        # seat1: 5m×2 + 11 张其他
        hand1 = Counter({MAN5: 2})
        pool[MAN5] -= 2
        if pool[MAN5] == 0:
            del pool[MAN5]
        hand1.update(take_n(pool, 11))
        # seat0: 含 5m 的 14 张
        hand0 = take_n(pool, 13)
        hand0[MAN5] += 1
        pool[MAN5] -= 1
        if pool[MAN5] == 0:
            del pool[MAN5]
        hand2 = take_n(pool, 13)
        hand3 = take_n(pool, 13)

        b = BoardState(
            hands=(hand0, hand1, hand2, hand3),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=(),
            melds=b0.melds,
            last_draw_tile=None,
            last_draw_was_rinshan=False,
            rinshan_draw_index=0,
            call_state=None,
            riichi=(False, False, False, False),
            ippatsu_eligible=frozenset(),
            double_riichi=frozenset(),
            all_discards_per_seat=((), (), (), ()),
            called_discard_indices=(frozenset(), frozenset(), frozenset(), frozenset()),
        )

        # seat0 打出 5m
        b1 = apply_discard(b, 0, MAN5)
        assert b1.turn_phase == TurnPhase.CALL_RESPONSE
        # seat1 有 5m×2，可以碰
        assert b1.hands[1][MAN5] >= 2


# --- 大明杠（daiminkan）测试 ---

class TestDaiminkanClaim:
    """大明杠路径覆盖。"""

    def test_daiminkan_window_state(self) -> None:
        """构造大明杠应答窗口状态。"""
        # seat0 打出 9p，seat1 有三张 9p 可以大明杠
        b0 = board_sorted_deal(dealer=0)
        pool = pool_not_in_wall(b0)
        # seat1: 9p×3 + 10 张其他
        hand1 = Counter({PIN9: 3})
        pool[PIN9] -= 3
        if pool[PIN9] == 0:
            del pool[PIN9]
        hand1.update(take_n(pool, 10))
        # seat0: 含 9p 的 14 张
        hand0 = take_n(pool, 13)
        hand0[PIN9] += 1
        pool[PIN9] -= 1
        if pool[PIN9] == 0:
            del pool[PIN9]
        hand2 = take_n(pool, 13)
        hand3 = take_n(pool, 13)

        b = BoardState(
            hands=(hand0, hand1, hand2, hand3),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=(),
            melds=b0.melds,
            last_draw_tile=None,
            last_draw_was_rinshan=False,
            rinshan_draw_index=0,
            call_state=None,
            riichi=(False, False, False, False),
            ippatsu_eligible=frozenset(),
            double_riichi=frozenset(),
            all_discards_per_seat=((), (), (), ()),
            called_discard_indices=(frozenset(), frozenset(), frozenset(), frozenset()),
        )

        # seat0 打出 9p
        b1 = apply_discard(b, 0, PIN9)
        assert b1.turn_phase == TurnPhase.CALL_RESPONSE
        # seat1 有 9p×3，可以大明杠
        assert b1.hands[1][PIN9] >= 3


# --- 荣和窗口测试 ---

class TestRonWindow:
    """荣和应答窗口覆盖。"""

    def test_ron_window_state(self) -> None:
        """构造荣和应答窗口状态。"""
        # seat1 七对子听牌，seat0 打出和牌
        t7m = MAN7
        b0 = board_sorted_deal(dealer=0)
        pool = pool_not_in_wall(b0)
        # seat1: 6 对 + 1 单张 = 13 张
        hand1 = Counter({
            MAN1: 2, MAN2: 2, MAN3: 2, MAN4: 2, MAN5: 2, PIN1: 2, t7m: 1,
        })
        for t, n in hand1.items():
            pool[t] -= n
            if pool[t] == 0:
                del pool[t]
        # seat0: 含 7m 的 14 张
        hand0 = take_n(pool, 13)
        hand0[t7m] += 1
        pool[t7m] -= 1
        if pool[t7m] == 0:
            del pool[t7m]
        hand2 = take_n(pool, 13)
        hand3 = take_n(pool, 13)

        b = BoardState(
            hands=(hand0, hand1, hand2, hand3),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=(),
            melds=b0.melds,
            last_draw_tile=None,
            last_draw_was_rinshan=False,
            rinshan_draw_index=0,
            call_state=None,
            riichi=(False, False, False, False),
            ippatsu_eligible=frozenset(),
            double_riichi=frozenset(),
            all_discards_per_seat=((), (), (), ()),
            called_discard_indices=(frozenset(), frozenset(), frozenset(), frozenset()),
        )

        # seat0 打出 7m
        b1 = apply_discard(b, 0, t7m)
        assert b1.turn_phase == TurnPhase.CALL_RESPONSE
        # seat1 可以荣和
        assert can_ron_default(b1.hands[1], b1.melds[1], t7m) is True


# --- 摸打循环中的 call window 清除 ---

class TestCallWindowClear:
    """call window 清除路径覆盖。"""

    def test_clear_call_window_after_discard(self) -> None:
        """打牌后 call window 能被正确清除。"""
        b = board_sorted_deal(dealer=0)
        # 亲家打一张
        tile = next(iter(b.hands[0].elements()))
        b = apply_discard(b, 0, tile)
        assert b.turn_phase == TurnPhase.CALL_RESPONSE
        # 清除 call window
        b = clear_call_window(b)
        assert b.turn_phase == TurnPhase.NEED_DRAW

    def test_multiple_rounds_with_call_window(self) -> None:
        """多轮摸打中 call window 反复清除。"""
        b = board_sorted_deal(dealer=0)
        # 亲家先打一张（配牌后 MUST_DISCARD，无 last_draw_tile）
        tile = next(iter(b.hands[0].elements()))
        b = apply_discard(b, 0, tile)
        b = clear_call_window(b)
        # 后续轮次：摸 → 打（摸切）→ 清 call window
        for _ in range(10):
            b = apply_draw(b, b.current_seat)
            drawn = b.last_draw_tile
            assert drawn is not None
            b = apply_discard(b, b.current_seat, drawn)
            b = clear_call_window(b)
