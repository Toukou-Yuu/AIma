"""役满类型测试。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    GameState,
    Suit,
    Tile,
    apply,
    build_deck,
    initial_game_state,
    shuffle_deck,
)
from kernel.deal.model import BoardState
from kernel.hand.melds import Meld, MeldKind
from kernel.play.model import RiverEntry, TurnPhase
from kernel.scoring.yaku import (
    _is_chinroutou,
    _is_chuuren_poutou,
    _is_daisangen,
    _is_daisuushii,
    _is_junsei_chuuren_poutou,
    _is_kokushi_musou,
    _is_kokushi_thirteen_waits,
    _is_ryuuiisou,
    _is_shou_suushii,
    _is_suu_kantsu,
    _is_suuankou,
    _is_suuankou_tanki,
    _is_tsuuiisou,
    count_yaku_han,
)
from kernel.table.model import MatchPreset, PrevailingWind, RoundNumber, initial_table_snapshot
from kernel import build_board_after_split, split_wall, BoardState


def _board_sorted_deal(*, dealer: int = 0) -> BoardState:
    """未洗牌牌山，测试用砌牌可复现。"""
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


class TestDaisangen:
    """大三元测试。"""

    def test_daisangen_basic(self) -> None:
        """大三元：三元牌三组刻子。"""
        c: Counter[Tile] = Counter()
        # 白三张
        c[Tile(Suit.HONOR, 5)] = 3
        # 发三张
        c[Tile(Suit.HONOR, 6)] = 3
        # 中三张
        c[Tile(Suit.HONOR, 7)] = 3
        # 雀头（任意）
        c[Tile(Suit.MAN, 1)] = 2
        # 剩余一张（荣和的牌）
        c[Tile(Suit.MAN, 2)] = 1

        assert _is_daisangen(c) is True

    def test_daisangen_with_melds(self) -> None:
        """大三元：副露 + 门内。"""
        c: Counter[Tile] = Counter()
        # 门内：中三张
        c[Tile(Suit.HONOR, 7)] = 3
        # 雀头
        c[Tile(Suit.MAN, 1)] = 2

        melds = (
            Meld(kind=MeldKind.PON, tiles=[Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 5)], from_seat=1),
            Meld(kind=MeldKind.PON, tiles=[Tile(Suit.HONOR, 6), Tile(Suit.HONOR, 6), Tile(Suit.HONOR, 6)], from_seat=2),
        )

        full = c.copy()
        for m in melds:
            for t in m.tiles:
                full[t] += 1

        assert _is_daisangen(full) is True

    def test_not_daisangen_missing_one_dragon(self) -> None:
        """不是大三元：缺一组三元牌。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.HONOR, 5)] = 3  # 白
        c[Tile(Suit.HONOR, 6)] = 3  # 发
        # 中没有刻子
        c[Tile(Suit.HONOR, 7)] = 1
        c[Tile(Suit.MAN, 1)] = 5

        assert _is_daisangen(c) is False


class TestSuuankou:
    """四暗刻测试。"""

    def test_suuankou_basic(self) -> None:
        """四暗刻：门前清四暗刻 + 一对。"""
        c: Counter[Tile] = Counter()
        # 四组暗刻
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 9)] = 3
        c[Tile(Suit.PIN, 1)] = 3
        c[Tile(Suit.PIN, 9)] = 3
        # 雀头
        c[Tile(Suit.SOU, 1)] = 2

        melds: tuple[Meld, ...] = ()
        win_tile = Tile(Suit.SOU, 1)

        assert _is_suuankou(c, melds, win_tile, for_ron=False) is True

    def test_suuankou_tanki_basic(self) -> None:
        """四暗刻单骑：荣和时五对子形。"""
        c: Counter[Tile] = Counter()
        # 三组暗刻
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 9)] = 3
        c[Tile(Suit.PIN, 1)] = 3
        # 两组对子（其中一组是单骑待牌）
        c[Tile(Suit.PIN, 9)] = 2
        c[Tile(Suit.SOU, 1)] = 2

        melds: tuple[Meld, ...] = ()
        win_tile = Tile(Suit.SOU, 1)  # 荣和这张成刻

        assert _is_suuankou_tanki(c, melds, win_tile, for_ron=True) is True

    def test_suuankou_not_with_melds(self) -> None:
        """四暗刻：有副露则不是。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 9)] = 3
        c[Tile(Suit.PIN, 1)] = 3

        melds = (
            Meld(kind=MeldKind.PON, tiles=[Tile(Suit.PIN, 9), Tile(Suit.PIN, 9), Tile(Suit.PIN, 9)], from_seat=1),
        )
        c[Tile(Suit.SOU, 1)] = 2

        win_tile = Tile(Suit.SOU, 1)

        assert _is_suuankou(c, melds, win_tile, for_ron=False) is False


class TestKokushiMusou:
    """国士无理测试。"""

    def test_kokushi_basic(self) -> None:
        """国士无理：十三幺九各一张 + 一对。"""
        c: Counter[Tile] = Counter()
        # 十三种幺九牌各一张
        terminals = [
            Tile(Suit.MAN, 1), Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1), Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1), Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1), Tile(Suit.HONOR, 2), Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4), Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ]
        for t in terminals:
            c[t] = 1
        # 再加一张形成对子（假设是中）
        c[Tile(Suit.HONOR, 7)] = 2

        melds: tuple[Meld, ...] = ()

        assert _is_kokushi_musou(c, melds) is True

    def test_kokushi_thirteen_waits(self) -> None:
        """国士十三面：十三种幺九牌各一张。"""
        c: Counter[Tile] = Counter()
        terminals = [
            Tile(Suit.MAN, 1), Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1), Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1), Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1), Tile(Suit.HONOR, 2), Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4), Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ]
        for t in terminals:
            c[t] = 1

        melds: tuple[Meld, ...] = ()
        win_tile = Tile(Suit.HONOR, 7)  # 荣和成对

        assert _is_kokushi_thirteen_waits(c, melds, win_tile) is True

    def test_kokushi_not_with_melds(self) -> None:
        """国士：有副露则不是。"""
        c: Counter[Tile] = Counter()
        for rank in [1, 9]:
            c[Tile(Suit.MAN, rank)] = 1
            c[Tile(Suit.PIN, rank)] = 1
            c[Tile(Suit.SOU, rank)] = 1
        for rank in range(1, 8):
            c[Tile(Suit.HONOR, rank)] = 1
        c[Tile(Suit.HONOR, 7)] = 2

        melds = (
            Meld(kind=MeldKind.CHI, tiles=[Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3)], from_seat=1),
        )

        assert _is_kokushi_musou(c, melds) is False


class TestChinroutou:
    """清老头测试。"""

    def test_chinroutou_basic(self) -> None:
        """清老头：仅 19 数牌。"""
        c: Counter[Tile] = Counter()
        # 19 数牌
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 9)] = 3
        c[Tile(Suit.PIN, 1)] = 3
        c[Tile(Suit.PIN, 9)] = 3
        c[Tile(Suit.SOU, 1)] = 2

        melds: tuple[Meld, ...] = ()

        assert _is_chinroutou(c, melds) is True

    def test_chinroutou_not_with_honor(self) -> None:
        """清老头：有字牌则不是。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 9)] = 3
        c[Tile(Suit.PIN, 1)] = 3
        c[Tile(Suit.PIN, 9)] = 3
        c[Tile(Suit.HONOR, 1)] = 2  # 字牌

        melds: tuple[Meld, ...] = ()

        assert _is_chinroutou(c, melds) is False


class TestTsuuiisou:
    """字一色测试。"""

    def test_tsuuiisou_basic(self) -> None:
        """字一色：仅字牌。"""
        c: Counter[Tile] = Counter()
        # 字牌
        c[Tile(Suit.HONOR, 1)] = 3
        c[Tile(Suit.HONOR, 2)] = 3
        c[Tile(Suit.HONOR, 3)] = 3
        c[Tile(Suit.HONOR, 4)] = 3
        c[Tile(Suit.HONOR, 5)] = 2

        melds: tuple[Meld, ...] = ()

        assert _is_tsuuiisou(c, melds) is True

    def test_tsuuiisou_not_with_suit(self) -> None:
        """字一色：有数牌则不是。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.HONOR, 1)] = 3
        c[Tile(Suit.HONOR, 2)] = 3
        c[Tile(Suit.HONOR, 3)] = 3
        c[Tile(Suit.MAN, 1)] = 3  # 数牌
        c[Tile(Suit.HONOR, 5)] = 2

        melds: tuple[Meld, ...] = ()

        assert _is_tsuuiisou(c, melds) is False


class TestRyuuiisou:
    """绿一色测试。"""

    def test_ryuuiisou_basic(self) -> None:
        """绿一色：仅 23468 索 + 发。"""
        c: Counter[Tile] = Counter()
        # 绿一色允许的牌
        c[Tile(Suit.SOU, 2)] = 3
        c[Tile(Suit.SOU, 3)] = 3
        c[Tile(Suit.SOU, 4)] = 3
        c[Tile(Suit.SOU, 6)] = 3
        c[Tile(Suit.HONOR, 6)] = 2  # 发

        melds: tuple[Meld, ...] = ()

        assert _is_ryuuiisou(c, melds) is True

    def test_ryuuiisou_not_with_other_sou(self) -> None:
        """绿一色：有其他索子则不是。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.SOU, 2)] = 3
        c[Tile(Suit.SOU, 3)] = 3
        c[Tile(Suit.SOU, 4)] = 3
        c[Tile(Suit.SOU, 5)] = 3  # 5 索不是绿一色
        c[Tile(Suit.HONOR, 6)] = 2

        melds: tuple[Meld, ...] = ()

        assert _is_ryuuiisou(c, melds) is False


class TestChuurenPoutou:
    """九莲宝灯测试。"""

    def test_chuuren_poutou_basic(self) -> None:
        """九莲宝灯：1112345678999 + 1 张。"""
        c: Counter[Tile] = Counter()
        # 基础形 1112345678999
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 2)] = 1
        c[Tile(Suit.MAN, 3)] = 1
        c[Tile(Suit.MAN, 4)] = 1
        c[Tile(Suit.MAN, 5)] = 1
        c[Tile(Suit.MAN, 6)] = 1
        c[Tile(Suit.MAN, 7)] = 1
        c[Tile(Suit.MAN, 8)] = 1
        c[Tile(Suit.MAN, 9)] = 3
        # 额外一张（假设是 5）
        c[Tile(Suit.MAN, 5)] += 1

        melds: tuple[Meld, ...] = ()
        win_tile = Tile(Suit.MAN, 5)

        assert _is_chuuren_poutou(c, melds, win_tile) is True

    def test_junsei_chuuren_poutou(self) -> None:
        """纯正九莲宝灯：九面待。"""
        c: Counter[Tile] = Counter()
        # 1112345678999（13 张）
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 2)] = 1
        c[Tile(Suit.MAN, 3)] = 1
        c[Tile(Suit.MAN, 4)] = 1
        c[Tile(Suit.MAN, 5)] = 1
        c[Tile(Suit.MAN, 6)] = 1
        c[Tile(Suit.MAN, 7)] = 1
        c[Tile(Suit.MAN, 8)] = 1
        c[Tile(Suit.MAN, 9)] = 3

        melds: tuple[Meld, ...] = ()
        win_tile = Tile(Suit.MAN, 5)  # 待任意牌

        assert _is_junsei_chuuren_poutou(c, melds, win_tile) is True

    def test_chuuren_poutou_not_with_melds(self) -> None:
        """九莲宝灯：有副露则不是。"""
        c: Counter[Tile] = Counter()
        c[Tile(Suit.MAN, 1)] = 3
        c[Tile(Suit.MAN, 9)] = 3

        melds = (
            Meld(kind=MeldKind.CHI, tiles=[Tile(Suit.MAN, 2), Tile(Suit.MAN, 3), Tile(Suit.MAN, 4)], from_seat=1),
        )

        win_tile = Tile(Suit.MAN, 5)

        assert _is_chuuren_poutou(c, melds, win_tile) is False


class TestSuuKantsu:
    """四杠子测试。"""

    def test_suu_kantsu_basic(self) -> None:
        """四杠子：四组杠子。"""
        melds = (
            Meld(kind=MeldKind.DAIMINKAN, tiles=[Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1)], from_seat=0),
            Meld(kind=MeldKind.ANKAN, tiles=[Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9)], from_seat=0),
            Meld(kind=MeldKind.DAIMINKAN, tiles=[Tile(Suit.PIN, 1), Tile(Suit.PIN, 1), Tile(Suit.PIN, 1), Tile(Suit.PIN, 1)], from_seat=0),
            Meld(kind=MeldKind.ANKAN, tiles=[Tile(Suit.PIN, 9), Tile(Suit.PIN, 9), Tile(Suit.PIN, 9), Tile(Suit.PIN, 9)], from_seat=0),
        )

        assert _is_suu_kantsu(melds) is True

    def test_suu_kantsu_not_three_kan(self) -> None:
        """四杠子：三组杠子则不是。"""
        melds = (
            Meld(kind=MeldKind.DAIMINKAN, tiles=[Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1), Tile(Suit.MAN, 1)], from_seat=0),
            Meld(kind=MeldKind.ANKAN, tiles=[Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9), Tile(Suit.MAN, 9)], from_seat=0),
            Meld(kind=MeldKind.DAIMINKAN, tiles=[Tile(Suit.PIN, 1), Tile(Suit.PIN, 1), Tile(Suit.PIN, 1), Tile(Suit.PIN, 1)], from_seat=0),
        )

        assert _is_suu_kantsu(melds) is False


class TestSuushii:
    """四喜测试。"""

    def test_daisuushii_basic(self) -> None:
        """大四喜：四风四组刻子。"""
        c: Counter[Tile] = Counter()
        # 四风刻子
        c[Tile(Suit.HONOR, 1)] = 3  # 东
        c[Tile(Suit.HONOR, 2)] = 3  # 南
        c[Tile(Suit.HONOR, 3)] = 3  # 西
        c[Tile(Suit.HONOR, 4)] = 3  # 北

        melds: tuple[Meld, ...] = ()

        assert _is_daisuushii(c, melds) is True

    def test_shou_suushii_basic(self) -> None:
        """小四喜：四风三组刻子 + 一对。"""
        c: Counter[Tile] = Counter()
        # 三组风牌刻子
        c[Tile(Suit.HONOR, 1)] = 3  # 东
        c[Tile(Suit.HONOR, 2)] = 3  # 南
        c[Tile(Suit.HONOR, 3)] = 3  # 西
        # 一对风牌
        c[Tile(Suit.HONOR, 4)] = 2  # 北

        melds: tuple[Meld, ...] = ()

        assert _is_shou_suushii(c, melds) is True


class TestYakumanHan:
    """役满番数测试。"""

    def test_daisangen_han(self) -> None:
        """大三元：13 番。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        c[Tile(Suit.HONOR, 5)] = 3
        c[Tile(Suit.HONOR, 6)] = 3
        c[Tile(Suit.HONOR, 7)] = 3
        c[Tile(Suit.MAN, 1)] = 2

        win_tile = Tile(Suit.MAN, 2)
        c[win_tile] = 1

        han = count_yaku_han(
            board, table, 0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        assert han == 13

    def test_kokushi_han(self) -> None:
        """国士无理：13 番。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        terminals = [
            Tile(Suit.MAN, 1), Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1), Tile(Suit.PIN, 9),
            Tile(Suit.SOU, 1), Tile(Suit.SOU, 9),
            Tile(Suit.HONOR, 1), Tile(Suit.HONOR, 2), Tile(Suit.HONOR, 3),
            Tile(Suit.HONOR, 4), Tile(Suit.HONOR, 5), Tile(Suit.HONOR, 6),
            Tile(Suit.HONOR, 7),
        ]
        for t in terminals:
            c[t] = 1
        c[Tile(Suit.HONOR, 7)] = 2  # 对子

        win_tile = Tile(Suit.HONOR, 7)

        han = count_yaku_han(
            board, table, 0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        assert han == 13

    def test_tsuuiisou_han(self) -> None:
        """字一色：13 番。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        c[Tile(Suit.HONOR, 1)] = 3
        c[Tile(Suit.HONOR, 2)] = 3
        c[Tile(Suit.HONOR, 3)] = 3
        c[Tile(Suit.HONOR, 4)] = 3
        c[Tile(Suit.HONOR, 5)] = 2

        win_tile = Tile(Suit.HONOR, 5)

        han = count_yaku_han(
            board, table, 0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )
        assert han == 13
