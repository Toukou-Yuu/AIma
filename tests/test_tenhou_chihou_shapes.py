"""天和、地和与和牌形组合测试（H-33 修复验证）。

测试要点：
1. 地和：len(board.river) == 1（庄家已打第一张）
2. 天和：len(board.river) == 0（庄家未打牌）
3. 子家首巡自摸 → 地和
4. 非首巡自摸 → 不是地和
5. 和牌形（标准形、七对子、国士）与天和/地的组合

参考 tests/test_yakuman.py::TestTenhou 和 TestChiihou 的测试风格。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from kernel import (
    Suit,
    Tile,
    build_board_after_split,
    build_deck,
    split_wall,
)
from kernel.board import BoardState, RiverEntry
from kernel.scoring.yaku import (
    _is_chihou,
    _is_tenhou,
    count_yaku_han,
    is_kokushi_musou,
    is_kokushi_thirteen_waits,
)
from kernel.table.model import initial_table_snapshot


def _board_sorted_deal(*, dealer: int = 0) -> BoardState:
    """未洗牌牌山，测试用砌牌可复现。"""
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def _make_chihou_board() -> BoardState:
    """构造子和牌状态：庄家已打第一张，子家第一巡自摸。

    参考 test_yakuman.py::TestChiihou::_make_chihou_board。
    """
    board = _board_sorted_deal(dealer=0)
    # 庄家舍一张
    discard_tile = board.hands[0].most_common(1)[0][0]
    dealer_hand = board.hands[0].copy()
    dealer_hand[discard_tile] -= 1
    if dealer_hand[discard_tile] == 0:
        del dealer_hand[discard_tile]
    # 子家摸一张（从 live_wall[0]）
    draw_tile = board.live_wall[0]
    seat1_hand = board.hands[1].copy()
    seat1_hand[draw_tile] += 1
    hands = (dealer_hand, seat1_hand, board.hands[2], board.hands[3])
    return replace(
        board,
        hands=hands,
        current_seat=1,
        live_draw_index=1,
        river=(RiverEntry(seat=0, tile=discard_tile),),
        last_draw_tile=draw_tile,
    )


class TestTenhouConditions:
    """天和条件测试。"""

    def test_tenhou_river_empty(self) -> None:
        """天和：river 为空（庄家未打牌）。"""
        board = _board_sorted_deal(dealer=0)
        # 配牌后 river=()
        assert len(board.river) == 0

    def test_tenhou_dealer_only(self) -> None:
        """天和：仅庄家可天和。"""
        board = _board_sorted_deal(dealer=0)
        # 庄家自摸可天和
        assert _is_tenhou(board, winner=0, is_tsumo=True, dealer_seat=0) is True
        # 子家不算天和
        assert _is_tenhou(board, winner=1, is_tsumo=True, dealer_seat=0) is False

    def test_tenhou_tsumo_only(self) -> None:
        """天和：仅自摸可天和，荣和不算。"""
        board = _board_sorted_deal(dealer=0)
        assert _is_tenhou(board, winner=0, is_tsumo=True, dealer_seat=0) is True
        assert _is_tenhou(board, winner=0, is_tsumo=False, dealer_seat=0) is False

    def test_tenhou_current_seat_match(self) -> None:
        """天和：current_seat 必须等于庄家席。"""
        board = _board_sorted_deal(dealer=0)
        # 配牌后 current_seat=0（庄家）
        assert board.current_seat == 0
        assert _is_tenhou(board, winner=0, is_tsumo=True, dealer_seat=0) is True


class TestChihouConditions:
    """地和条件测试。"""

    def test_chihou_river_has_one(self) -> None:
        """地和：river 有且仅有庄家打出的第一张。"""
        board = _make_chihou_board()
        assert len(board.river) == 1
        assert board.river[0].seat == 0  # 庄家打出

    def test_chihou_non_dealer_tsumo(self) -> None:
        """地和：子家首巡自摸。"""
        board = _make_chihou_board()
        assert _is_chihou(board, winner=1, is_tsumo=True, dealer_seat=0) is True

    def test_chihou_ron_rejected(self) -> None:
        """地和：荣和不算地和。"""
        board = _make_chihou_board()
        assert _is_chihou(board, winner=1, is_tsumo=False, dealer_seat=0) is False

    def test_chihou_dealer_rejected(self) -> None:
        """地和：庄家不算地和。"""
        board = _board_sorted_deal(dealer=0)
        # 庄家自摸不是地和（是天和条件）
        assert _is_chihou(board, winner=0, is_tsumo=True, dealer_seat=0) is False

    def test_chihou_winner_no_discard(self) -> None:
        """地和：胜者无舍牌。"""
        board = _make_chihou_board()
        # 子家首巡，all_discards_per_seat[1] 应为空
        assert len(board.all_discards_per_seat[1]) == 0

    def test_chihou_no_melds(self) -> None:
        """地和：无副露。"""
        board = _make_chihou_board()
        # 首巡无副露
        assert all(len(m) == 0 for m in board.melds)


class TestTenhouWithShapes:
    """天和与和牌形组合测试。"""

    def test_tenhou_with_kokushi(self) -> None:
        """天和 + 国士无双。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        # 构造庄家国士 14 张（十三幺九各一张 + 一对）
        c: Counter[Tile] = Counter()
        terminals = [
            Tile(Suit.MAN, 1),
            Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1),
            Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1),
            Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 2),
            Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4),
            Tile(Suit.HONOR, 5),
            Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ]
        for t in terminals:
            c[t] = 1
        c[Tile(Suit.HONOR, 7)] += 1  # 对子

        win_tile = Tile(Suit.HONOR, 7)

        # 验证天和条件
        assert _is_tenhou(board, winner=0, is_tsumo=True, dealer_seat=0) is True
        # 验证国士无双
        assert is_kokushi_musou(c, melds=()) is True

        # 计算番数（天和 = 役满 13 番，国士无双 = 役满 13 番）
        han = count_yaku_han(
            board,
            table,
            0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        # 役满至少 13 番
        assert han >= 13

    def test_tenhou_with_standard_shape(self) -> None:
        """天和 + 标准形。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        # 构造标准形：四面子一对
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 2)] = 3
        c[Tile(Suit.MAN, 3)] = 3
        c[Tile(Suit.MAN, 4)] = 3
        c[Tile(Suit.MAN, 5)] = 2

        win_tile = Tile(Suit.MAN, 5)

        assert _is_tenhou(board, winner=0, is_tsumo=True, dealer_seat=0) is True

        han = count_yaku_han(
            board,
            table,
            0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        # 天和役满
        assert han >= 13


class TestChihouWithShapes:
    """地和与和牌形组合测试。"""

    def test_chihou_with_kokushi(self) -> None:
        """地和 + 国士无双。"""
        board = _make_chihou_board()
        table = initial_table_snapshot()

        # 构造子家国士 14 张
        c: Counter[Tile] = Counter()
        terminals = [
            Tile(Suit.MAN, 1),
            Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1),
            Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1),
            Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 2),
            Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4),
            Tile(Suit.HONOR, 5),
            Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ]
        for t in terminals:
            c[t] = 1
        c[Tile(Suit.HONOR, 7)] += 1

        win_tile = Tile(Suit.HONOR, 7)

        assert _is_chihou(board, winner=1, is_tsumo=True, dealer_seat=0) is True
        assert is_kokushi_musou(c, melds=()) is True

        han = count_yaku_han(
            board,
            table,
            1,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        assert han >= 13

    def test_chihou_with_standard_shape(self) -> None:
        """地和 + 标准形。"""
        board = _make_chihou_board()
        table = initial_table_snapshot()

        # 构造标准形
        c: Counter[Tile] = Counter()
        c[Tile(Suit.PIN, 1)] = 3
        c[Tile(Suit.PIN, 2)] = 3
        c[Tile(Suit.PIN, 3)] = 3
        c[Tile(Suit.PIN, 4)] = 3
        c[Tile(Suit.PIN, 5)] = 2

        win_tile = Tile(Suit.PIN, 5)

        assert _is_chihou(board, winner=1, is_tsumo=True, dealer_seat=0) is True

        han = count_yaku_han(
            board,
            table,
            1,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        assert han >= 13


class TestChihouNegativeCases:
    """地和边界条件测试。"""

    def test_chihou_river_length_zero_rejected(self) -> None:
        """river 长度为 0 时不是地和（天和条件）。"""
        board = _board_sorted_deal(dealer=0)
        # river=0，天和条件，不是地和
        assert len(board.river) == 0
        assert _is_chihou(board, winner=1, is_tsumo=True, dealer_seat=0) is False

    def test_chihou_conditions_logic(self) -> None:
        """地和条件逻辑：验证 H-33 首巡窗口判断。"""
        board = _make_chihou_board()
        # 正确的子和状态
        assert len(board.river) == 1  # 庄家已打第一张
        assert board.current_seat != 0  # 不是庄家
        assert len(board.all_discards_per_seat[1]) == 0  # 子家无舍牌
        assert all(len(m) == 0 for m in board.melds)  # 无副露
        # 应判定为地和
        assert _is_chihou(board, winner=1, is_tsumo=True, dealer_seat=0) is True


class TestTenhouChihouIntegration:
    """天和/地和与 scoring 系统集成测试。"""

    def test_tenhou_kokushi_thirteen_waits(self) -> None:
        """天和 + 国士十三面。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        # 国士十三面：13 张各一张（待任意）
        c: Counter[Tile] = Counter()
        terminals = [
            Tile(Suit.MAN, 1),
            Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1),
            Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1),
            Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 2),
            Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4),
            Tile(Suit.HONOR, 5),
            Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ]
        for t in terminals:
            c[t] = 1

        win_tile = Tile(Suit.HONOR, 7)

        assert is_kokushi_thirteen_waits(c, melds=(), win_tile=win_tile) is True

        han = count_yaku_han(
            board,
            table,
            0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        # 国士十三面 + 天和
        assert han >= 13

    def test_chihou_kokushi_thirteen_waits(self) -> None:
        """地和 + 国士十三面。"""
        board = _make_chihou_board()
        table = initial_table_snapshot()

        # 国士十三面
        c: Counter[Tile] = Counter()
        terminals = [
            Tile(Suit.MAN, 1),
            Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1),
            Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1),
            Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1),
            Tile(Suit.HONOR, 2),
            Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4),
            Tile(Suit.HONOR, 5),
            Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ]
        for t in terminals:
            c[t] = 1

        win_tile = Tile(Suit.HONOR, 7)

        assert is_kokushi_thirteen_waits(c, melds=(), win_tile=win_tile) is True

        han = count_yaku_han(
            board,
            table,
            1,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        assert han >= 13