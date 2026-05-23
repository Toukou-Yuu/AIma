"""H-29 国士无双计分回归测试。

测试要点：
1. 普通国士荣和（13张门内 + win_tile）-> 13番 "国士无双"
2. 国士十三面荣和 -> 13番 "国士无双十三面"
3. 国士自摸（14张）-> 正确标签区分
4. 非十三面待牌的国士 -> 正确区分
"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import Suit, Tile, build_board_after_split, build_deck, split_wall
from kernel.board import BoardState
from kernel.scoring.yaku import count_yaku_han, non_dora_yaku_han_and_labels
from kernel.table.model import initial_table_snapshot


def _board_sorted_deal(*, dealer: int = 0) -> BoardState:
    """未洗牌牌山，测试用砌牌可复现。"""
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


# 十三种幺九牌
TERMINALS = [
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


class TestKokushiRonScoring:
    """国士无双荣和计分测试。"""

    def test_kokushi_ron_13_han(self) -> None:
        """普通国士荣和：13张门内 + win_tile = 14张，应为 13番 '国士无双'。

        场景：手牌 13 张，11 种幺九牌各 1 张 + 中（HONOR7）2 张对子，
        荣和北（HONOR4）完成国士。

        荣和后牌形：12 种各 1 张 + 中 2 张 = 普通国士（非十三面）。
        """
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        # 11 种幺九牌各 1 张（不含北 HONOR4）
        for t in TERMINALS[:9]:  # MAN1, MAN9, PIN1, PIN9, SOU1, SOU9, 东, 南, 西
            c[t] = 1
        c[Tile(Suit.HONOR, 5)] = 1  # 白
        c[Tile(Suit.HONOR, 6)] = 1  # 发
        # 中有 2 张对子
        c[Tile(Suit.HONOR, 7)] = 2

        # 荣和北（HONOR4）成为第 12 种牌的第 1 张
        win_tile = Tile(Suit.HONOR, 4)

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=True,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=False,
        )

        assert han == 13
        assert "国士无双" in labels
        assert "国士无双十三面" not in labels

    def test_kokushi_thirteen_waits_ron_13_han(self) -> None:
        """国士十三面荣和：13张门内各 1 张，荣和任意幺九牌成对。

        场景：手牌 13 张，恰好是 13 种幺九牌各 1 张，
        荣和任意一张幺九牌都成国士十三面。
        """
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        # 13 种幺九牌各 1 张
        for t in TERMINALS:
            c[t] = 1

        # 荣和东风成对
        win_tile = Tile(Suit.HONOR, 1)

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=True,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=False,
        )

        assert han == 13
        assert "国士无双十三面" in labels
        assert "国士无双" not in labels or "国士无双十三面" in labels

    def test_kokushi_ron_different_wait_tile(self) -> None:
        """普通国士荣和：非十三面待牌。

        场景：手牌 13 张，有一对，但不是十三面听牌，
        确保正确区分普通国士与十三面。
        """
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        # 11 种幺九牌各 1 张
        for t in TERMINALS[:11]:
            c[t] = 1
        # 第 12 种（发）有 2 张对子
        c[Tile(Suit.HONOR, 6)] = 2

        # 荣和第 13 种幺九牌（中）
        win_tile = Tile(Suit.HONOR, 7)

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=True,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=False,
        )

        assert han == 13
        assert "国士无双" in labels
        assert "国士无双十三面" not in labels


class TestKokushiTsumoScoring:
    """国士无双自摸计分测试。"""

    def test_kokushi_tsumo_13_han(self) -> None:
        """普通国士自摸：14张门内，应为 13番 '国士无双'。

        场景：自摸后 14 张，11 种幺九牌各 1 张 + 北（HONOR4）1 张 + 中（HONOR7）2 张。
        自摸前是 11 种各 1 张 + 中 2 张（13 张），自摸北后成普通国士。

        注：自摸前牌形（移除北后）不是十三面，因为已有中对子。
        """
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        # 11 种幺九牌各 1 张（不含北）
        for t in TERMINALS[:9]:
            c[t] = 1
        c[Tile(Suit.HONOR, 5)] = 1  # 白
        c[Tile(Suit.HONOR, 6)] = 1  # 发
        # 北 1 张（自摸的）
        c[Tile(Suit.HONOR, 4)] = 1
        # 中 2 张（原有对子）
        c[Tile(Suit.HONOR, 7)] = 2

        # 自摸牌是北
        win_tile = Tile(Suit.HONOR, 4)

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )

        assert han == 13
        assert "国士无双" in labels
        assert "国士无双十三面" not in labels

    def test_kokushi_thirteen_waits_tsumo_13_han(self) -> None:
        """国士十三面自摸：14张门内，自摸前 13 种各 1 张。

        场景：自摸前 13 张是十三面听牌，自摸任意幺九牌成十三面。
        """
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        # 13 种幺九牌各 1 张
        for t in TERMINALS:
            c[t] = 1
        # 自摸的牌形成一对
        c[Tile(Suit.HONOR, 7)] += 1

        # 自摸牌
        win_tile = Tile(Suit.HONOR, 7)

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )

        assert han == 13
        assert "国士无双十三面" in labels
        assert "国士无双" not in labels or "国士无双十三面" in labels

    def test_kokushi_tsumo_different_wait_tile(self) -> None:
        """普通国士自摸：非十三面待牌，非天和状态。

        场景：自摸前已有对子，非十三面听牌。
        使用非首巡状态的 board 避免触发天和判断。
        """
        from dataclasses import replace

        from kernel.board import RiverEntry

        # 构造非首巡状态：亲家舍牌 + 自摸（非首巡）
        board = _board_sorted_deal(dealer=0)

        # 亲家舍牌
        discard1 = board.hands[0].most_common(1)[0][0]
        dealer_hand = board.hands[0].copy()
        dealer_hand[discard1] -= 1
        if dealer_hand[discard1] == 0:
            del dealer_hand[discard1]

        # 亲家摸牌（构造自摸状态）
        draw_tile = board.live_wall[0]
        dealer_hand[draw_tile] += 1

        board = replace(
            board,
            hands=(dealer_hand, board.hands[1], board.hands[2], board.hands[3]),
            river=(RiverEntry(seat=0, tile=discard1),),
            current_seat=0,
            live_draw_index=1,
            last_draw_tile=draw_tile,
        )

        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        # 10 种幺九牌各 1 张（不含北、发）
        for t in TERMINALS[:9]:
            c[t] = 1
        c[Tile(Suit.HONOR, 5)] = 1  # 白
        # 发有 2 张对子（已有对子）
        c[Tile(Suit.HONOR, 6)] = 2
        # 北 1 张 + 中 1 张（中是自摸的）
        c[Tile(Suit.HONOR, 4)] = 1
        c[Tile(Suit.HONOR, 7)] = 1

        # 自摸牌是中
        win_tile = Tile(Suit.HONOR, 7)

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,  # 亲家
            for_ron=False,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=True,
        )

        assert han == 13
        assert "国士无双" in labels
        assert "国士无双十三面" not in labels
        assert "天和" not in labels


class TestKokushiEdgeCases:
    """国士无双边界情况测试。"""

    def test_kokushi_not_with_melds(self) -> None:
        """国士无双：有副露则不算。"""
        from kernel.hand.melds import Meld, MeldKind

        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        c: Counter[Tile] = Counter()
        for t in TERMINALS[:12]:
            c[t] = 1
        c[Tile(Suit.HONOR, 7)] = 2

        win_tile = Tile(Suit.HONOR, 4)

        melds = (
            Meld(
                kind=MeldKind.CHI,
                tiles=[Tile(Suit.MAN, 1), Tile(Suit.MAN, 2), Tile(Suit.MAN, 3)],
                from_seat=1,
            ),
        )

        # 将副露的牌加入 concealed 以满足 14 张
        for m in melds:
            for t in m.tiles:
                c[t] += 1

        han = count_yaku_han(
            board,
            table,
            winner=0,
            for_ron=True,
            win_tile=win_tile,
            concealed=c,
            melds=melds,
            is_tsumo=False,
        )

        # 有副露则不是国士，应该走一般形判断（这里可能无役）
        assert han < 13  # 不是役满

    def test_kokushi_thirteen_waits_all_terminals_valid(self) -> None:
        """国士十三面：验证 13 种幺九牌任意荣和都算十三面。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        for win_tile in TERMINALS:
            c: Counter[Tile] = Counter()
            for t in TERMINALS:
                c[t] = 1

            han, labels = non_dora_yaku_han_and_labels(
                board,
                table,
                winner=0,
                for_ron=True,
                win_tile=win_tile,
                concealed=c,
                melds=(),
                is_tsumo=False,
            )

            assert han == 13, f"荣和 {win_tile} 应该是役满"
            assert "国士无双十三面" in labels, f"荣和 {win_tile} 应该是十三面"


class TestKokushiLabelConsistency:
    """国士无双标签一致性测试。"""

    def test_label_vs_han_count_consistency(self) -> None:
        """验证 han == 13 时标签正确。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        # 十三面荣和
        c: Counter[Tile] = Counter()
        for t in TERMINALS:
            c[t] = 1
        win_tile = Tile(Suit.HONOR, 1)

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=True,
            win_tile=win_tile,
            concealed=c,
            melds=(),
            is_tsumo=False,
        )

        assert han == 13
        assert any("国士" in label for label in labels)

    def test_thirteen_waits_label_distinction(self) -> None:
        """十三面与普通国士标签区分明确。"""
        board = _board_sorted_deal(dealer=0)
        table = initial_table_snapshot()

        # 十三面：手牌 13 张各 1 张
        c13: Counter[Tile] = Counter()
        for t in TERMINALS:
            c13[t] = 1

        han13, labels13 = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=True,
            win_tile=Tile(Suit.HONOR, 1),
            concealed=c13,
            melds=(),
            is_tsumo=False,
        )

        # 普通国士：手牌 11 种各 1 张 + 中对子 2 张，荣和北
        c_normal: Counter[Tile] = Counter()
        for t in TERMINALS[:9]:
            c_normal[t] = 1
        c_normal[Tile(Suit.HONOR, 5)] = 1  # 白
        c_normal[Tile(Suit.HONOR, 6)] = 1  # 发
        c_normal[Tile(Suit.HONOR, 7)] = 2  # 中对子

        han_normal, labels_normal = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=True,
            win_tile=Tile(Suit.HONOR, 4),  # 荣和北
            concealed=c_normal,
            melds=(),
            is_tsumo=False,
        )

        # 两者番数相同
        assert han13 == 13
        assert han_normal == 13

        # 标签必须不同
        assert labels13 != labels_normal, "十三面和普通国士标签必须区分"
        assert "国士无双十三面" in labels13
        assert "国士无双" in labels_normal and "国士无双十三面" not in labels_normal