"""win_shape.std 杠子面子计数测试：H-30 修复验证。

H-30: 杠子物理上是 4 张，但结构上只占 1 个面子（3 张结构牌）。
"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, MeldKind
from kernel.tiles.model import Suit, Tile
from kernel.win_shape.std import can_win_standard_form, can_win_standard_form_concealed_total

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
SOU1 = Tile(Suit.SOU, 1)
SOU2 = Tile(Suit.SOU, 2)
SOU3 = Tile(Suit.SOU, 3)


class TestOneAnkanStandardForm:
    """1个暗杠 + 标准形测试。"""

    def test_one_ankan_three_sets_one_pair(self) -> None:
        """暗杠(4张物理=3张结构) + 三面子(9张) + 雀头(2张) = 14张结构。

        concealed: 门内牌（不含和牌），需要 11 张
        - 三面子: 234m + 567m + 123p = 9 张
        - 雀头: 1s × 1 张（和牌会补充第 2 张）
        win_tile: 1s
        合计: 9 + 1 = 10 张... 不对

        正确计算：
        - 暗杠: 3 张结构
        - 门内需: 14 - 3 = 11 张（含和牌）
        - concealed 不含和牌，所以 concealed 有 10 张
        - concealed + win_tile = 11 张
        """
        # 暗杠: 1111m
        ankan = Meld(MeldKind.ANKAN, (MAN1, MAN1, MAN1, MAN1), None)

        # 门内（不含和牌）: 234m + 567m + 123p + 1s = 10 张
        # 和牌后: 234m + 567m + 123p + 11s = 11 张
        concealed: Counter[Tile] = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1,  # 234m
            MAN5: 1, MAN6: 1, MAN7: 1,  # 567m
            PIN1: 1, PIN2: 1, PIN3: 1,  # 123p
            SOU1: 1,  # 1s（和牌后变成雀头）
        })
        win_tile = SOU1  # 自摸 1s

        # 验证: concealed(10) + win_tile(1) + 暗杠结构(3) = 14 张结构
        assert can_win_standard_form(concealed, (ankan,), win_tile) is True

    def test_one_ankan_with_honor_pair(self) -> None:
        """暗杠 + 字牌雀头的标准形。"""
        # 暗杠: 1111m
        ankan = Meld(MeldKind.ANKAN, (MAN1, MAN1, MAN1, MAN1), None)

        # 门内（不含和牌）: 234m + 567m + 123p + 东 = 10 张
        EAST = Tile(Suit.HONOR, 1)
        concealed: Counter[Tile] = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1,  # 234m
            MAN5: 1, MAN6: 1, MAN7: 1,  # 567m
            PIN1: 1, PIN2: 1, PIN3: 1,  # 123p
            EAST: 1,  # 东（和牌后变成雀头）
        })
        win_tile = EAST

        assert can_win_standard_form(concealed, (ankan,), win_tile) is True


class TestTwoAnkanStandardForm:
    """2个暗杠 + 标准形测试。"""

    def test_two_ankan_two_sets_one_pair(self) -> None:
        """两个暗杠(8张物理=6张结构) + 两面子(6张) + 雀头(2张) = 14张结构。

        - 两个暗杠: 6 张结构
        - 门内需: 14 - 6 = 8 张（含和牌）
        - concealed 不含和牌，所以 concealed 有 7 张
        """
        # 两个暗杠: 1111m, 2222m
        ankan1 = Meld(MeldKind.ANKAN, (MAN1, MAN1, MAN1, MAN1), None)
        ankan2 = Meld(MeldKind.ANKAN, (MAN2, MAN2, MAN2, MAN2), None)

        # 门内（不含和牌）: 123p + 456p + 1s = 7 张
        concealed: Counter[Tile] = Counter({
            PIN1: 1, PIN2: 1, PIN3: 1,  # 123p
            PIN4: 1, PIN5: 1, PIN6: 1,  # 456p
            SOU1: 1,  # 1s（和牌后变成雀头）
        })
        win_tile = SOU1

        # 验证: concealed(7) + win_tile(1) + 两个暗杠结构(6) = 14 张结构
        assert can_win_standard_form(concealed, (ankan1, ankan2), win_tile) is True

    def test_two_ankan_concealed_total(self) -> None:
        """can_win_standard_form_concealed_total: 门内已含和牌的情况。

        两个暗杠(6张结构) + 门内(8张，已含和牌) = 14 张结构。
        """
        ankan1 = Meld(MeldKind.ANKAN, (MAN1, MAN1, MAN1, MAN1), None)
        ankan2 = Meld(MeldKind.ANKAN, (MAN2, MAN2, MAN2, MAN2), None)

        # 门内（已含和牌）: 123p + 456p + 11s = 8 张
        concealed: Counter[Tile] = Counter({
            PIN1: 1, PIN2: 1, PIN3: 1,
            PIN4: 1, PIN5: 1, PIN6: 1,
            SOU1: 2,
        })

        # 验证: concealed(8) + 两个暗杠结构(6) = 14 张结构
        assert can_win_standard_form_concealed_total(concealed, (ankan1, ankan2)) is True


class TestKanWithOtherMelds:
    """杠 + 其他副露 + 标准形测试。"""

    def test_ankan_plus_pon(self) -> None:
        """暗杠 + 碰(明刻) + 两面子 + 雀头。

        - 暗杠: 3 张结构
        - 碰: 3 张结构
        - 门内需: 14 - 6 = 8 张（含和牌）
        - concealed 不含和牌，所以 7 张
        """
        # 暗杠: 1111m
        ankan = Meld(MeldKind.ANKAN, (MAN1, MAN1, MAN1, MAN1), None)
        # 碰: 111p
        pon = Meld(MeldKind.PON, (PIN1, PIN1, PIN1), PIN1)

        # 门内（不含和牌）: 234m + 567m + 1s = 7 张
        concealed: Counter[Tile] = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1,  # 234m
            MAN5: 1, MAN6: 1, MAN7: 1,  # 567m
            SOU1: 1,  # 1s（和牌后变成雀头）
        })
        win_tile = SOU1

        # 验证: concealed(7) + win_tile(1) + 暗杠(3) + 碰(3) = 14 张结构
        assert can_win_standard_form(concealed, (ankan, pon), win_tile) is True

    def test_daiminkan_with_standard_form(self) -> None:
        """大明杠 + 标准形测试。"""
        # 大明杠: 1111m
        daiminkan = Meld(MeldKind.DAIMINKAN, (MAN1, MAN1, MAN1, MAN1), MAN1)

        # 门内（不含和牌）: 234m + 567m + 123p + 1s = 10 张
        concealed: Counter[Tile] = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1,
            MAN5: 1, MAN6: 1, MAN7: 1,
            PIN1: 1, PIN2: 1, PIN3: 1,
            SOU1: 1,
        })
        win_tile = SOU1

        # 验证: concealed(10) + win_tile(1) + 大明杠结构(3) = 14 张结构
        assert can_win_standard_form(concealed, (daiminkan,), win_tile) is True

    def test_kakan_with_standard_form(self) -> None:
        """加杠 + 标准形测试。"""
        # 加杠: 1111m
        kakan = Meld(MeldKind.KAKAN, (MAN1, MAN1, MAN1, MAN1), None)

        # 门内（不含和牌）: 234m + 567m + 123p + 1s = 10 张
        concealed: Counter[Tile] = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1,
            MAN5: 1, MAN6: 1, MAN7: 1,
            PIN1: 1, PIN2: 1, PIN3: 1,
            SOU1: 1,
        })
        win_tile = SOU1

        assert can_win_standard_form(concealed, (kakan,), win_tile) is True


class TestKanTileCountValidation:
    """验证 H-30 修复：杠子按结构张数计算，而非物理张数。"""

    def test_four_ankan_should_pass(self) -> None:
        """四个暗杠 = 4 个面子 = 12 张结构，门内必须只有雀头。

        四个暗杠 = 12 张结构，门内需要 2 张雀头（含和牌）。
        concealed 不含和牌，所以只有 1 张。
        """
        ankan1 = Meld(MeldKind.ANKAN, (MAN1, MAN1, MAN1, MAN1), None)
        ankan2 = Meld(MeldKind.ANKAN, (MAN2, MAN2, MAN2, MAN2), None)
        ankan3 = Meld(MeldKind.ANKAN, (MAN3, MAN3, MAN3, MAN3), None)
        ankan4 = Meld(MeldKind.ANKAN, (MAN4, MAN4, MAN4, MAN4), None)

        # 门内（不含和牌）只有单张 1s，和牌后变成雀头
        concealed: Counter[Tile] = Counter({SOU1: 1})
        win_tile = SOU1

        # 验证: concealed(1) + win_tile(1) + 四个暗杠结构(12) = 14 张结构
        assert can_win_standard_form(concealed, (ankan1, ankan2, ankan3, ankan4), win_tile) is True

    def test_mixed_kan_types(self) -> None:
        """混合杠类型测试：暗杠 + 大明杠 + 加杠。"""
        ankan = Meld(MeldKind.ANKAN, (MAN1, MAN1, MAN1, MAN1), None)
        daiminkan = Meld(MeldKind.DAIMINKAN, (MAN2, MAN2, MAN2, MAN2), MAN2)
        kakan = Meld(MeldKind.KAKAN, (MAN3, MAN3, MAN3, MAN3), None)

        # 3 个杠 = 9 张结构，门内需要 5 张（含和牌）
        # concealed 不含和牌，所以 4 张: 123p(3) + 1s(1) = 4 张
        concealed: Counter[Tile] = Counter({
            PIN1: 1, PIN2: 1, PIN3: 1,  # 123p
            SOU1: 1,  # 1s（和牌后变成雀头）
        })
        win_tile = SOU1

        # 验证: concealed(4) + win_tile(1) + 三个杠结构(9) = 14 张结构
        assert can_win_standard_form(concealed, (ankan, daiminkan, kakan), win_tile) is True