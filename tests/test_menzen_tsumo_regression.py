"""门前清自摸和回归测试：R-02 bug - is_tsumo 参数存在但未使用。

Bug: non_dora_yaku_han_and_labels 接收 is_tsumo=True 参数，
     但从未使用该参数添加"门前清自摸和" 1 番。

Test ID: T-RULE-MENZEN-TSUMO-003
"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, MeldKind
from kernel.scoring.yaku import non_dora_yaku_han_and_labels
from kernel.table.model import PrevailingWind, TableSnapshot, initial_table_snapshot
from kernel.tiles.model import Suit, Tile

# Tile constants
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


def _table(*, dealer: int = 0) -> TableSnapshot:
    return initial_table_snapshot(dealer_seat=dealer)


def _board_stub():
    """合法 BoardState stub，使用真实配牌。"""
    from kernel import build_board_after_split, build_deck, split_wall

    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=0)


class TestMenzenTsumoHan:
    """门前清自摸和回归测试（T-RULE-MENZEN-TSUMO-003）。"""

    def test_closed_hand_tsumo_should_have_menzen_tsumo_yaku(self) -> None:
        """闭门手自摸应获得门前清自摸和 1 番。

        牌例: 234m 567m 234p 567p 55s 自摸 5s（已包含）
        - 门前清自摸和: 1 番
        - 断幺九: 1 番（无 1/9/字牌）
        - 合计: 至少 2 番

        注意: 自摸时 concealed counter 已经包含 win_tile（14 张）。

        Bug 表现: 缺少门前清自摸和，实际只有 1 番。
        """
        board = _board_stub()
        table = _table()

        # 闭门手 14 张: 234m 567m 234p 567p 55s（自摸 5s 已包含）
        concealed = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1,
            MAN5: 1, MAN6: 1, MAN7: 1,
            PIN2: 1, PIN3: 1, PIN4: 1,
            PIN5: 1, PIN6: 1, PIN7: 1,
            SOU5: 2,  # 自摸 5s 已包含成对
        })

        win_tile = SOU5
        melds: tuple[Meld, ...] = ()  # 无副露，门前清

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=1,  # 避免天和判定
            for_ron=False,
            win_tile=win_tile,
            concealed=concealed,
            melds=melds,
            is_tsumo=True,  # 自摸
        )

        # 断幺九应该存在（无字牌、无 1/9）
        assert "断幺九" in labels, f"断幺九应被检测到，实际 labels={labels}"

        # 门前清自摸和应该存在（无副露 + 自摸）
        # BUG: 当前代码不会添加这个 yaku
        assert "门前清自摸和" in labels, f"门前清自摸和应被检测到（无副露+自摸），实际 labels={labels}"

        # 合计番数应至少为 2（门前清自摸和 1 + 断幺九 1）
        assert han >= 2, f"门前清自摸和+断幺九应至少 2 番，实际 han={han}, labels={labels}"

    def test_closed_hand_ron_should_not_have_menzen_tsumo_yaku(self) -> None:
        """闭门手荣和不应获得门前清自摸和。

        牌例同上，但荣和而非自摸。
        应只有断幺九 1 番，无门前清自摸和。
        """
        board = _board_stub()
        table = _table()

        # 闭门手 13 张: 234m 567m 234p 567p 5s
        # 荣和 5s 后成 14 张
        concealed = Counter({
            MAN2: 1, MAN3: 1, MAN4: 1,
            MAN5: 1, MAN6: 1, MAN7: 1,
            PIN2: 1, PIN3: 1, PIN4: 1,
            PIN5: 1, PIN6: 1, PIN7: 1,
            SOU5: 1,
        })

        win_tile = SOU5
        melds: tuple[Meld, ...] = ()

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=1,
            for_ron=True,  # 荣和
            win_tile=win_tile,
            concealed=concealed,
            melds=melds,
            is_tsumo=False,
        )

        # 断幺九应该存在
        assert "断幺九" in labels, f"断幺九应被检测到，实际 labels={labels}"

        # 门前清自摸和不应该存在（这是荣和）
        assert "门前清自摸和" not in labels, f"荣和不应有门前清自摸和，实际 labels={labels}"

    def test_open_hand_tsumo_should_not_have_menzen_tsumo_yaku(self) -> None:
        """副露手自摸不应获得门前清自摸和。

        牌例: chi 234m + 门内 567m 234p 567p 55s 自摸 5s（已包含）
        有吃副露，非门前清。
        应只有断幺九 1 番，无门前清自摸和。

        注意: 自摸时 concealed counter 已经包含 win_tile。
        """
        board = _board_stub()
        table = _table()

        # 有副露的牌例: chi 234m + 门内 567m 234p 567p 55s（自摸 5s 已包含）
        melds = (
            Meld(MeldKind.CHI, (MAN2, MAN3, MAN4), MAN3),
        )

        # 门内 11 张: 567m 234p 567p 55s
        concealed = Counter({
            MAN5: 1, MAN6: 1, MAN7: 1,
            PIN2: 1, PIN3: 1, PIN4: 1,
            PIN5: 1, PIN6: 1, PIN7: 1,
            SOU5: 2,
        })

        win_tile = SOU5

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=1,
            for_ron=False,
            win_tile=win_tile,
            concealed=concealed,
            melds=melds,
            is_tsumo=True,
        )

        # 断幺九应该存在（如果配置允许副露断幺）
        assert "断幺九" in labels, f"断幺九应被检测到，实际 labels={labels}"

        # 门前清自摸和不应该存在（有吃副露）
        assert "门前清自摸和" not in labels, f"副露手不应有门前清自摸和，实际 labels={labels}"

    def test_chiitoitsu_tsumo_should_have_menzen_tsumo_yaku(self) -> None:
        """七对子自摸应获得门前清自摸和。

        七对子本身就是门前清限定役种。
        自摸时应额外获得门前清自摸和 1 番。

        注意: 自摸时 concealed counter 已经包含 win_tile（14 张）。

        牌例: 22m 33m 44m 55p 66p 77p 88s 自摸 8s（已包含）
        - 七对子: 2 番
        - 门前清自摸和: 1 番
        - 断幺九: 1 番（无 1/9/字牌）
        - 合计: 4 番
        """
        board = _board_stub()
        table = _table()

        # 七对子 14 张: 22m 33m 44m 55p 66p 77p 88s（自摸 8s 已包含）
        concealed = Counter({
            MAN2: 2, MAN3: 2, MAN4: 2,
            PIN5: 2, PIN6: 2, PIN7: 2,
            SOU8: 2,
        })

        win_tile = SOU8
        melds: tuple[Meld, ...] = ()

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=1,
            for_ron=False,
            win_tile=win_tile,
            concealed=concealed,
            melds=melds,
            is_tsumo=True,
        )

        # 七对子应该存在
        assert "七对子" in labels, f"七对子应被检测到，实际 labels={labels}"

        # 断幺九应该存在
        assert "断幺九" in labels, f"断幺九应被检测到，实际 labels={labels}"

        # 门前清自摸和应该存在（七对子也是门前清，自摸应加番）
        assert "门前清自摸和" in labels, f"七对子自摸应有门前清自摸和，实际 labels={labels}"

        # 合计番数应至少为 4（七对子 2 + 门前清自摸和 1 + 断幺九 1）
        assert han >= 4, f"七对子自摸应至少 4 番，实际 han={han}, labels={labels}"


class TestMenzenTsumoWithAnkan:
    """暗杠后的门前清自摸和测试（R-03 相关）。

    暗杠不应破门清状态。
    """

    def test_ankan_should_not_break_menzen_tsumo(self) -> None:
        """暗杠后自摸应仍获得门前清自摸和。

        牌例: ankan 5555m + 门内 234p 567p 234s 55s 自摸 5s（已包含）
        暗杠不破门清，应获得门前清自摸和。

        注意: 自摸时 concealed counter 已经包含 win_tile。
        - 暗杠 melds: 4 张
        - concealed: 10 张（234p 567p 234s 55s）
        - 总计: 14 张

        预期会失败，因为当前 menzen 检查使用 len(melds)==0，
        暗杠作为 meld 会错误地认为非门前清。
        """
        board = _board_stub()
        table = _table()

        # 暗杠 5555m + 门内 234p 567p 234s 55s（自摸 5s 已包含）
        melds = (
            Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5)),
        )

        concealed = Counter({
            PIN2: 1, PIN3: 1, PIN4: 1,
            PIN5: 1, PIN6: 1, PIN7: 1,
            SOU2: 1, SOU3: 1, SOU4: 1,
            SOU5: 2,  # 自摸 5s 已包含成对
        })

        win_tile = SOU5

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=1,
            for_ron=False,
            win_tile=win_tile,
            concealed=concealed,
            melds=melds,
            is_tsumo=True,
        )

        # 断幺九应该存在
        assert "断幺九" in labels, f"断幺九应被检测到，实际 labels={labels}"

        # 门前清自摸和应该存在（暗杠不破门清）
        # BUG: 当前代码使用 len(melds)==0 判断门清，暗杠会错误破门清
        assert "门前清自摸和" in labels, f"暗杠后自摸应有门前清自摸和，实际 labels={labels}"

        # 合计番数应至少为 2
        assert han >= 2, f"暗杠后自摸应至少 2 番，实际 han={han}, labels={labels}"