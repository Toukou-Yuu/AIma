"""kan.declare 错误守卫覆盖缺口测试。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel.hand.melds import Meld, MeldKind
from kernel.kan.declare import apply_ankan, apply_kakan
from kernel.play.model import TurnPhase
from kernel.tiles.model import Suit, Tile
from tests.engine_helpers import board_sorted_deal, make_board_with_discard
from tests.call_helpers import clear_call_window

MAN1 = Tile(Suit.MAN, 1)
MAN2 = Tile(Suit.MAN, 2)
MAN3 = Tile(Suit.MAN, 3)
MAN5 = Tile(Suit.MAN, 5)
PIN5 = Tile(Suit.PIN, 5)


def _must_discard_board() -> "BoardState":
    """合法 MUST_DISCARD 状态（真实配牌，亲家 14 张）。"""
    return board_sorted_deal(dealer=0)


def _rinshan_board() -> "BoardState":
    """合法 MUST_DISCARD + last_draw_was_rinshan 状态：亲家 15 张（岭上摸后）。"""
    b = board_sorted_deal(dealer=0)
    # 模拟岭上摸：从 dead_wall.rinshan[0] 取一张加入亲家手牌
    extra = b.dead_wall.rinshan[0]
    new_hands = list(b.hands)
    h = new_hands[0].copy()
    h[extra] += 1
    new_hands[0] = h
    return replace(
        b,
        hands=tuple(new_hands),
        last_draw_tile=extra,
        last_draw_was_rinshan=True,
        rinshan_draw_index=1,
    )


def _need_draw_board() -> "BoardState":
    """合法 NEED_DRAW 状态：先打一张再清空 call window。"""
    b = board_sorted_deal(dealer=0)
    # 亲家打出 MAN1 到河里 → CALL_RESPONSE
    discard_tile = next(t for t in b.hands[0] if b.hands[0][t] >= 1)
    b2 = make_board_with_discard(
        dealer=0, discarder=0, discard_tile=discard_tile,
        discarder_hand=b.hands[0],
    )
    # 清空 call window → NEED_DRAW
    b3 = clear_call_window(b2)
    assert b3.turn_phase == TurnPhase.NEED_DRAW
    return b3


# --- apply_ankan error guards ---

class TestAnkanErrorGuards:
    def test_wrong_turn_phase(self) -> None:
        """NEED_DRAW 阶段尝试暗杠。"""
        b = _need_draw_board()
        # 用 current_seat 手中的牌构造暗杠（可能不是真正 4 张，但函数先检查 turn_phase）
        tile = next(iter(b.hands[b.current_seat]))
        meld = Meld(MeldKind.ANKAN, (tile, tile, tile, tile))
        try:
            apply_ankan(b, b.current_seat, meld)
            raise AssertionError("expected ValueError for ankan in NEED_DRAW")
        except ValueError:
            pass

    def test_wrong_seat(self) -> None:
        b = _must_discard_board()
        tile = next(iter(b.hands[0]))
        meld = Meld(MeldKind.ANKAN, (tile, tile, tile, tile))
        try:
            apply_ankan(b, 1, meld)
            raise AssertionError("expected ValueError for ankan wrong seat")
        except ValueError:
            pass

    def test_rinshan_pending(self) -> None:
        """last_draw_was_rinshan=True 时尝试暗杠。"""
        b = _rinshan_board()
        tile = b.last_draw_tile
        meld = Meld(MeldKind.ANKAN, (tile, tile, tile, tile))
        try:
            apply_ankan(b, 0, meld)
            raise AssertionError("expected ValueError for ankan with rinshan pending")
        except ValueError:
            pass


# --- apply_kakan error guards ---

class TestShankuminkanErrorGuards:
    def test_wrong_meld_kind(self) -> None:
        b = _must_discard_board()
        tile = next(iter(b.hands[0]))
        meld = Meld(MeldKind.PON, (tile, tile, tile), tile)
        try:
            apply_kakan(b, 0, meld)
            raise AssertionError("expected ValueError for kakan with non-KAKAN meld")
        except ValueError:
            pass

    def test_wrong_turn_phase(self) -> None:
        b = _need_draw_board()
        tile = next(iter(b.hands[b.current_seat]))
        meld = Meld(MeldKind.KAKAN, (tile, tile, tile, tile))
        try:
            apply_kakan(b, b.current_seat, meld)
            raise AssertionError("expected ValueError for kakan in NEED_DRAW")
        except ValueError:
            pass

    def test_wrong_seat(self) -> None:
        b = _must_discard_board()
        tile = next(iter(b.hands[0]))
        meld = Meld(MeldKind.KAKAN, (tile, tile, tile, tile))
        try:
            apply_kakan(b, 1, meld)
            raise AssertionError("expected ValueError for kakan wrong seat")
        except ValueError:
            pass

    def test_rinshan_pending(self) -> None:
        b = _rinshan_board()
        tile = b.last_draw_tile
        meld = Meld(MeldKind.KAKAN, (tile, tile, tile, tile))
        try:
            apply_kakan(b, 0, meld)
            raise AssertionError("expected ValueError for kakan with rinshan pending")
        except ValueError:
            pass

    def test_call_state_present(self) -> None:
        """CALL_RESPONSE 阶段尝试加杠。"""
        b = board_sorted_deal(dealer=0)
        tile = next(iter(b.hands[0]))
        b2 = make_board_with_discard(
            dealer=0, discarder=0, discard_tile=tile,
            discarder_hand=b.hands[0],
        )
        assert b2.turn_phase == TurnPhase.CALL_RESPONSE
        meld = Meld(MeldKind.KAKAN, (tile, tile, tile, tile))
        try:
            apply_kakan(b2, b2.current_seat, meld)
            raise AssertionError("expected ValueError for kakan during CALL_RESPONSE")
        except ValueError:
            pass

    def test_after_riichi(self) -> None:
        b = _must_discard_board()
        riichi_list = list(b.riichi)
        riichi_list[0] = True
        b2 = replace(b, riichi=tuple(riichi_list))
        tile = next(iter(b.hands[0]))
        meld = Meld(MeldKind.KAKAN, (tile, tile, tile, tile))
        try:
            apply_kakan(b2, 0, meld)
            raise AssertionError("expected ValueError for kakan after riichi")
        except ValueError:
            pass


# --- apply_after_kan_rinshan_draw error guards ---

class TestRinshanDrawErrorGuards:
    def test_wrong_turn_phase(self) -> None:
        from kernel.kan.rinshan import apply_after_kan_rinshan_draw
        b = _need_draw_board()
        try:
            apply_after_kan_rinshan_draw(b, b.current_seat)
            raise AssertionError("expected ValueError for rinshan in NEED_DRAW")
        except ValueError:
            pass

    def test_wrong_seat(self) -> None:
        from kernel.kan.rinshan import apply_after_kan_rinshan_draw
        b = _must_discard_board()
        try:
            apply_after_kan_rinshan_draw(b, 1)
            raise AssertionError("expected ValueError for rinshan wrong seat")
        except ValueError:
            pass

    def test_already_rinshan(self) -> None:
        from kernel.kan.rinshan import apply_after_kan_rinshan_draw
        b = _rinshan_board()
        # last_draw_was_rinshan=True 已设置，应报错
        try:
            apply_after_kan_rinshan_draw(b, 0)
            raise AssertionError("expected ValueError for chaining rinshan")
        except ValueError:
            pass
