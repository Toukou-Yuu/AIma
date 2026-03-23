"""赤宝牌与宝牌计数测试。"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel.hand.melds import Meld, MeldKind
from kernel.scoring.dora import (
    count_dora_in_tiles,
    count_dora_total,
    count_ura_dora_total,
    dora_from_indicators,
    successor_tile,
    _is_red_five_match,
)
from kernel.tiles.model import Suit, Tile
from kernel.tiles.deck import build_deck, shuffle_deck


class TestSuccessorTile:
    """宝牌指示后继牌测试。"""

    def test_successor_number_tile(self) -> None:
        """数牌：1→2, ..., 8→9, 9→1。"""
        assert successor_tile(Tile(Suit.MAN, 1)) == Tile(Suit.MAN, 2)
        assert successor_tile(Tile(Suit.MAN, 8)) == Tile(Suit.MAN, 9)
        assert successor_tile(Tile(Suit.MAN, 9)) == Tile(Suit.MAN, 1)

    def test_successor_honor_tile(self) -> None:
        """字牌：东→南→西→北→东。"""
        assert successor_tile(Tile(Suit.HONOR, 1)) == Tile(Suit.HONOR, 2)  # 东→南
        assert successor_tile(Tile(Suit.HONOR, 4)) == Tile(Suit.HONOR, 5)  # 北→东
        assert successor_tile(Tile(Suit.HONOR, 7)) == Tile(Suit.HONOR, 1)  # 北→东

    def test_successor_always_non_red(self) -> None:
        """宝牌始终是非赤牌。"""
        for suit in (Suit.MAN, Suit.PIN, Suit.SOU):
            for rank in range(1, 10):
                result = successor_tile(Tile(suit, rank))
                assert result.is_red is False


class TestRedFiveMatch:
    """赤五匹配测试。"""

    def test_normal_tile_matches_exact(self) -> None:
        """普通牌完全匹配。"""
        t = Tile(Suit.MAN, 3, False)
        d = Tile(Suit.MAN, 3, False)
        assert _is_red_five_match(t, d) is True

    def test_red_five_matches_normal_five_dora(self) -> None:
        """赤五匹配普通五宝牌。"""
        # 宝牌是 5（普通）
        dora = Tile(Suit.MAN, 5, False)
        # 赤五应该匹配
        assert _is_red_five_match(Tile(Suit.MAN, 5, True), dora) is True
        # 普通五也匹配
        assert _is_red_five_match(Tile(Suit.MAN, 5, False), dora) is True

    def test_red_five_not_match_other_dora(self) -> None:
        """赤五不匹配非五宝牌。"""
        dora = Tile(Suit.MAN, 4, False)
        assert _is_red_five_match(Tile(Suit.MAN, 5, True), dora) is False


class TestDoraFromIndicators:
    """宝牌指示牌测试。"""

    def test_dora_from_single_indicator(self) -> None:
        """单张指示牌。"""
        indicators = (Tile(Suit.MAN, 3),)
        dora = dora_from_indicators(indicators)
        assert dora == (Tile(Suit.MAN, 4),)

    def test_dora_from_multiple_indicators(self) -> None:
        """多张指示牌。"""
        indicators = (Tile(Suit.MAN, 8), Tile(Suit.PIN, 9), Tile(Suit.HONOR, 4))
        dora = dora_from_indicators(indicators)
        assert dora == (
            Tile(Suit.MAN, 9),
            Tile(Suit.PIN, 1),
            Tile(Suit.HONOR, 5),
        )


class TestCountDoraInTiles:
    """宝牌计数测试。"""

    def test_count_normal_dora(self) -> None:
        """普通宝牌计数。"""
        tiles = Counter()
        tiles[Tile(Suit.MAN, 4)] = 3
        tiles[Tile(Suit.MAN, 5)] = 2

        dora = (Tile(Suit.MAN, 4),)  # 宝牌是 4
        assert count_dora_in_tiles(tiles, dora) == 3

    def test_count_red_five_as_dora(self) -> None:
        """赤五算宝牌。"""
        tiles = Counter()
        tiles[Tile(Suit.MAN, 5, False)] = 2  # 普通五
        tiles[Tile(Suit.MAN, 5, True)] = 1   # 赤五

        dora = (Tile(Suit.MAN, 5, False),)  # 宝牌是 5
        assert count_dora_in_tiles(tiles, dora) == 3  # 全部算宝牌

    def test_count_red_five_only(self) -> None:
        """只有赤五的情况。"""
        tiles = Counter()
        tiles[Tile(Suit.SOU, 5, True)] = 1  # 赤五

        dora = (Tile(Suit.SOU, 5, False),)  # 宝牌是 5 索
        assert count_dora_in_tiles(tiles, dora) == 1


class TestCountDoraTotal:
    """总宝牌数计数测试。"""

    def test_count_dora_with_concealed_hand(self) -> None:
        """门内宝牌计数。"""
        concealed = Counter()
        concealed[Tile(Suit.MAN, 4)] = 4  # 4 张 4m

        dora_indicators = (Tile(Suit.MAN, 3),)  # 宝牌是 4m

        count = count_dora_total(
            concealed=concealed,
            melds=(),
            win_tile=Tile(Suit.MAN, 5),
            for_ron=False,
            revealed_indicators=dora_indicators,
        )
        assert count == 4

    def test_count_dora_with_melds(self) -> None:
        """副露含宝牌。"""
        concealed = Counter()
        concealed[Tile(Suit.MAN, 1)] = 3

        melds = (
            Meld(
                kind=MeldKind.PON,
                tiles=[Tile(Suit.MAN, 4), Tile(Suit.MAN, 4), Tile(Suit.MAN, 4)],
                from_seat=1,
            ),
        )

        dora_indicators = (Tile(Suit.MAN, 3),)  # 宝牌是 4m

        count = count_dora_total(
            concealed=concealed,
            melds=melds,
            win_tile=Tile(Suit.MAN, 5),
            for_ron=False,
            revealed_indicators=dora_indicators,
        )
        assert count == 3  # 副露的 3 张 4m

    def test_count_red_five_dora_in_meld(self) -> None:
        """副露含赤五。"""
        concealed = Counter()

        # 吃牌包含赤五
        melds = (
            Meld(
                kind=MeldKind.CHI,
                tiles=[Tile(Suit.SOU, 4, False), Tile(Suit.SOU, 5, True), Tile(Suit.SOU, 6, False)],
                from_seat=1,
            ),
        )

        dora_indicators = (Tile(Suit.SOU, 4),)  # 宝牌是 5 索

        count = count_dora_total(
            concealed=concealed,
            melds=melds,
            win_tile=Tile(Suit.SOU, 7),
            for_ron=False,
            revealed_indicators=dora_indicators,
        )
        assert count == 1  # 赤五算 1 宝牌


class TestUraDora:
    """里宝牌测试。"""

    def test_count_ura_dora(self) -> None:
        """里宝牌计数。"""
        concealed = Counter()
        concealed[Tile(Suit.MAN, 4)] = 2

        ura_indicators = (Tile(Suit.MAN, 3),)  # 里宝是 4m

        count = count_ura_dora_total(
            concealed=concealed,
            melds=(),
            win_tile=Tile(Suit.MAN, 5),
            for_ron=False,
            ura_indicators=ura_indicators,
        )
        assert count == 2

    def test_count_ura_dora_red_five(self) -> None:
        """里宝牌含赤五。"""
        concealed = Counter()
        concealed[Tile(Suit.PIN, 5, True)] = 1  # 赤五
        concealed[Tile(Suit.PIN, 5, False)] = 2  # 普通五

        ura_indicators = (Tile(Suit.PIN, 4),)  # 里宝是 5p

        count = count_ura_dora_total(
            concealed=concealed,
            melds=(),
            win_tile=Tile(Suit.PIN, 6),
            for_ron=False,
            ura_indicators=ura_indicators,
        )
        assert count == 3  # 赤五 + 2 张普通五


class TestBuildDeckWithRedFives:
    """牌山构建测试。"""

    def test_build_deck_has_three_red_fives(self) -> None:
        """三赤：5m/5p/5s 各 1 张赤牌。"""
        deck = build_deck(red_fives=True)

        red_five_man = sum(1 for t in deck if t.suit == Suit.MAN and t.rank == 5 and t.is_red)
        red_five_pin = sum(1 for t in deck if t.suit == Suit.PIN and t.rank == 5 and t.is_red)
        red_five_sou = sum(1 for t in deck if t.suit == Suit.SOU and t.rank == 5 and t.is_red)

        assert red_five_man == 1
        assert red_five_pin == 1
        assert red_five_sou == 1

    def test_build_deck_total_136(self) -> None:
        """总牌数 136 张。"""
        deck = build_deck(red_fives=True)
        assert len(deck) == 136

    def test_build_deck_no_red_fives(self) -> None:
        """无赤牌模式。"""
        deck = build_deck(red_fives=False)

        red_count = sum(1 for t in deck if t.is_red)
        assert red_count == 0
