"""R-04 回归测试：七对子不应给役牌对子加番。

役牌（役牌）需要刻子/杠子（>=3 张）。七对子只有对子，不应获得役牌番。
七对子固定 2 番 25 符。

根因：
- `_yakuhai_han_chiitoitsu_pairs()` 错误地为役牌对子加番
- `_yakuhai_labels_chiitoitsu_pairs()` 错误地返回役牌标签
- yaku.py:943-944 在 chiitoitsu 路径中调用了这些函数
"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel.hand.melds import Meld
from kernel.scoring.yaku import (
    non_dora_yaku_han_and_labels,
)
from kernel.table.model import PrevailingWind, TableSnapshot, initial_table_snapshot
from kernel.tiles.model import Suit, Tile

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
SOU1 = Tile(Suit.SOU, 1)
SOU2 = Tile(Suit.SOU, 2)
SOU3 = Tile(Suit.SOU, 3)
# 字牌
TON = Tile(Suit.HONOR, 1)  # 东风
NAN = Tile(Suit.HONOR, 2)  # 南风
SHA = Tile(Suit.HONOR, 3)  # 西风
PEI = Tile(Suit.HONOR, 4)  # 北风
HAKU = Tile(Suit.HONOR, 5)  # 白
HATSU = Tile(Suit.HONOR, 6)  # 发
CHUN = Tile(Suit.HONOR, 7)  # 中


def _board_stub():
    """合法 BoardState stub，使用真实配牌。"""
    from kernel import build_board_after_split, build_deck, split_wall

    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=0)


def _board_with_dealer(dealer: int):
    """合法 BoardState stub，指定亲家席次。"""
    from kernel import build_board_after_split, build_deck, split_wall

    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


def _table(*, dealer: int = 0, prevailing_wind: PrevailingWind = PrevailingWind.EAST) -> TableSnapshot:
    """创建 TableSnapshot，可指定亲家和场风。"""
    return initial_table_snapshot(dealer_seat=dealer, prevailing_wind=prevailing_wind)


# --- 端到端测试：验证 chiitoitsu 路径不加役牌番 ---


class TestChiitoitsuEndToEnd:
    """端到端测试：验证 non_dora_yaku_han_and_labels 中 chiitoitsu 路径不加役牌番。

    使用纯数牌七对子避免触发混一色等额外役。
    """

    def test_chiitoitsu_no_yakuhai_labels(self) -> None:
        """七对子不应有役牌标签。

        使用纯数牌避免触发混一色。验证 chiitoitsu 路径的 labels 输出。
        """
        # 纯万字七对子（不触发混一色，不触发役牌）
        # concealed: 13 张（7m 单张 + 6 对），win_tile=7m
        concealed = Counter({
            MAN1: 2,
            MAN2: 2,
            MAN3: 2,
            MAN4: 2,
            MAN5: 2,
            MAN6: 2,
            MAN7: 1,
        })
        board = _board_stub()
        table = _table()
        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            0,
            for_ron=True,
            win_tile=MAN7,
            concealed=concealed,
            melds=(),
            is_tsumo=False,
        )
        # 验证：七对子 2 番 + 清一色门清 6 番 = 8 畩
        # 关键：不应有任何役牌标签
        assert han == 8, f"Expected 8 han (chiitoitsu + chinitsu), got {han}"
        assert "七对子" in labels
        assert "清一色(门清)" in labels
        # 不应有任何役牌标签
        yakuhai_labels = ["白对", "发对", "中对", "场风对", "自风对", "连风对"]
        for yl in yakuhai_labels:
            assert yl not in labels, f"Unexpected yakuhai label '{yl}' in {labels}"

    def test_chiitoitsu_with_dragon_pair_han_count(self) -> None:
        """七对子带白对子：验证番数不应包含役牌番。

        使用万字+白，触发混一色。验证番数计算。
        """
        # 万字+白七对子（触发混一色）
        # concealed: 13 张（白单张 + 6 对万字），win_tile=白
        concealed = Counter({
            HAKU: 1,
            MAN1: 2,
            MAN2: 2,
            MAN3: 2,
            MAN4: 2,
            MAN5: 2,
            MAN6: 2,
        })
        board = _board_stub()
        table = _table()
        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            0,
            for_ron=True,
            win_tile=HAKU,
            concealed=concealed,
            melds=(),
            is_tsumo=False,
        )
        # 预期：七对子 2 + 混一色门清 3 = 5 番
        # BUG：当前是 2 + 1（白对） + 3 = 6 畩
        assert han == 5, f"Expected 5 han (chiitoitsu + honitsu), got {han}"
        assert "七对子" in labels
        assert "混一色(门清)" in labels
        assert "白对" not in labels

    def test_chiitoitsu_with_double_wind_pair_han_count(self) -> None:
        """七对子带连风对子：验证番数不应包含 2 番役牌番。

        seat 0 是 dealer，场风东，自风东 → 连风。
        """
        # 万字+东风七对子
        # concealed: 13 张（东风单张 + 6 对万字），win_tile=东风
        concealed = Counter({
            TON: 1,
            MAN1: 2,
            MAN2: 2,
            MAN3: 2,
            MAN4: 2,
            MAN5: 2,
            MAN6: 2,
        })
        board = _board_with_dealer(0)
        table = _table(dealer=0, prevailing_wind=PrevailingWind.EAST)
        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            0,  # winner = seat 0（连风）
            for_ron=True,
            win_tile=TON,
            concealed=concealed,
            melds=(),
            is_tsumo=False,
        )
        # 预期：七对子 2 + 混一色门清 3 = 5 畩
        # BUG：当前是 2 + 2（连风对） + 3 = 7 畩
        assert han == 5, f"Expected 5 han (chiitoitsu + honitsu), got {han}"
        assert "连风对" not in labels


# --- 对比测试：刻子计役牌，对子不计 ---


class TestYakuhaiNeedsTriplet:
    """役牌必须要有刻子（>=3 张），对子不计役牌番。"""

    def test_triplet_dragon_counts_yakuhai(self) -> None:
        """白刻子（非七对子）应该计役牌番。

        使用副露牌型避免触发役满。
        """
        # 副露：白刻子 + 顺子 + 其他
        from kernel.hand.melds import Meld, MeldKind

        concealed = Counter({
            MAN2: 1,
            MAN3: 1,
            MAN4: 1,  # 顺子
            PIN2: 2,  # 雀头
        })
        melds = (
            Meld(MeldKind.PON, (HAKU, HAKU, HAKU), HAKU),  # 白刻子副露
        )
        board = _board_stub()
        table = _table()
        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            0,
            for_ron=True,
            win_tile=PIN2,
            concealed=concealed,
            melds=melds,
            is_tsumo=False,
        )
        # 应该有役牌番
        assert "白刻" in labels, f"Expected '白刻' in labels, got {labels}"

    def test_pair_dragon_no_yakuhai(self) -> None:
        """白对子（非七对子）不应计役牌番。"""
        # 普通形：白对子（不是七对子）
        # 自摸：concealed 14 张，含 win_tile
        concealed = Counter({
            HAKU: 2,  # 白对子
            MAN1: 3,
            MAN2: 3,
            MAN3: 3,
            MAN4: 3,
        })
        board = _board_stub()
        table = _table()
        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            0,
            for_ron=False,
            win_tile=HAKU,
            concealed=concealed,
            melds=(),
            is_tsumo=True,
        )
        # 对子不应计役牌番
        assert "白刻" not in labels
        assert "白对" not in labels


# --- 边界测试：七对子可叠加其他役 ---


class TestChiitoitsuCombination:
    """七对子可与其他役叠加（不含役牌番）。"""

    def test_chiitoitsu_with_tanyao(self) -> None:
        """七对子 + 断幺九：应叠加计 2 + 1 = 3 番。"""
        # 断幺九七对子：2-8 的数牌
        concealed = Counter({
            MAN2: 1,  # 单张等待
            MAN3: 2,
            MAN4: 2,
            MAN5: 2,
            PIN2: 2,
            PIN3: 2,
            PIN4: 2,
        })
        board = _board_stub()
        table = _table()
        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            0,
            for_ron=True,
            win_tile=MAN2,
            concealed=concealed,
            melds=(),
            is_tsumo=False,
        )
        # 七对子 2 番 + 断幺九 1 番 = 3 畩
        assert han == 3, f"Expected 3 han, got {han}"
        assert "七对子" in labels
        assert "断幺九" in labels