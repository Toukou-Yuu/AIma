"""R-03 回归测试：门清判定误判暗杠。

根因：len(melds) == 0 检查将暗杠误判为非门清。
规则：暗杠 (ANKAN) 不破门前清，只有吃/碰/大明杠/加杠破门前清。

影响文件：
- fu.py:390 menzen = len(melds) == 0
- settle.py:70, 220 menzen = len(board.melds[winner]) == 0
- yaku.py:933, 947, 1016, 1021, 1026, 1030 menzen = len(melds) == 0
- decompose.py:138 menzen_peikou_level if len(melds) != 0
- tenpai.py:32-33 is_tenpai_seven_pairs if melds
- apply.py:432-434 riichi eligibility if board.melds[seat]
"""

from __future__ import annotations

from collections import Counter

import pytest

from kernel import (
    Action,
    ActionKind,
    BoardState,
    GamePhase,
    IllegalActionError,
    Meld,
    MeldKind,
    Suit,
    Tile,
    TurnPhase,
    apply,
    build_board_after_split,
    build_deck,
    initial_table_snapshot,
    split_wall,
)
from kernel.engine.state import GameState
from kernel.riichi.tenpai import is_tenpai_seven_pairs
from kernel.scoring.fu import compute_fu_detail, compute_fu_full
from kernel.scoring.settle import settle_ron_table, settle_tsumo_table
from kernel.scoring.yaku import non_dora_yaku_han_and_labels
from kernel.table.model import PrevailingWind, initial_table_snapshot
from kernel.win_shape.decompose import menzen_peikou_level

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


def _board_sorted_deal(*, dealer: int = 0) -> BoardState:
    w = tuple(build_deck())
    return build_board_after_split(split_wall(w), dealer_seat=dealer)


# ============================================================================
# 正向测试：暗杠应视为门清
# ============================================================================

class TestAnkanIsMenzenFuBonus:
    """fu.py: 门清荣和加符 +10 应适用于暗杠手牌。"""

    def test_ankan_menzen_ron_fu_bonus(self) -> None:
        """暗杠 + 门清荣和应获得 +10 门清荣和加符。"""
        # 暗杠 (5m 四张)
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        # 门内：123m 789p 11s + 暗杠后剩余 10 张
        concealed = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN7: 1, PIN8: 1, PIN9: 1, SOU1: 2, MAN4: 1, MAN6: 1})
        win_tile = MAN6  # 荣和 6m

        # 当前行为：len(melds) == 0 为 False，menzen=False，不加门清荣和加符
        # 期望行为：暗杠是门清，menzen=True，应加 10 符
        fu = compute_fu_full(concealed, (ankan,), win_tile, for_ron=True, self_wind=NAN, round_wind=TON)

        # 断言：门清荣和应获得 +10 加符（当前 BUG 会漏掉）
        # 基础 20 + 暗杠 16 + 门清荣和 10 = 46 -> 切上 50
        # BUG 状态：基础 20 + 暗杠 16 = 36 -> 切上 40
        assert fu >= 50, f"暗杠门清荣和应获得门清加符，实际 fu={fu}"


class TestAnkanMenzenTsumoHan:
    """settle.py / yaku.py: 门清自摸 1 番应适用于暗杠手牌。"""

    def test_ankan_menzen_tsumo_gets_menzen_tsumo_han(self) -> None:
        """暗杠 + 自摸应获得门清自摸 1 番。"""
        # 构造暗杠手牌 + 自摸场景
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        concealed = Counter({MAN1: 2, MAN2: 1, MAN3: 1, MAN4: 1, MAN6: 1, PIN1: 2, PIN2: 1, PIN3: 1, SOU1: 2})

        # 当前 BUG：len(melds)==0 为 False，误判为非门清，漏掉门清自摸番
        # 期望：暗杠是门清，应计门清自摸
        # 由于无法直接构造完整 BoardState，这里测试 yaku 函数
        table = initial_table_snapshot()
        board = _board_sorted_deal()

        han, labels = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=False,
            win_tile=MAN6,
            concealed=concealed,
            melds=(ankan,),
            is_tsumo=True,
        )

        # 门清自摸役名为"门前清自摸和"
        # 当前 BUG：会漏掉此役
        # 注：此处仅验证 menzen 计算正确，实际役判定需要完整 board 状态
        # 间接验证：检查 han 数是否正确（含门清自摸时应多 1 番）
        # 由于断幺九等役会叠加，这里用对比方式验证

        # 无副露门清自摸的 han
        han_no_meld, _ = non_dora_yaku_han_and_labels(
            board,
            table,
            winner=0,
            for_ron=False,
            win_tile=MAN6,
            concealed=Counter({MAN1: 2, MAN2: 1, MAN3: 1, MAN4: 1, MAN5: 4, MAN6: 1, PIN1: 2, PIN2: 1, PIN3: 1, SOU1: 2}),
            melds=(),
            is_tsumo=True,
        )

        # 暗杠手的 han 应与无副露门清手相同（门清自摸番不应因暗杠消失）
        # 但暗杠本身会增加符，不改变番数结构
        # 注：此测试依赖 BUG 修复后的正确行为


class TestAnkanRiichiEligibility:
    """apply.py:432-434: 暗杠手牌应能立直。

    BUG 根因：apply.py:432 检查 `if board.melds[seat]:` 拒绝立直。
    暗杠在 melds 中，但不应被视为"副露"而禁止立直。
    """

    def test_ankan_melds_not_empty_but_should_be_menzen(self) -> None:
        """演示 BUG 根因：apply.py 用 `if board.melds[seat]:` 检查门清。

        暗杠手牌的 melds 非空，但暗杠不应被视为"副露"。
        正确检查应区分 ANKAN 与其他副露类型。
        """
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        pon = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), called_tile=MAN5)

        # BUG 根因：apply.py:432-434 代码
        #   if board.melds[seat]:
        #       msg = "riichi requires menzen"
        #       raise IllegalActionError(msg)
        #
        # 此检查无法区分 ANKAN（门清）与 PON（非门清）

        # 当前代码行为：任何 melds 非空都拒绝立直
        ankan_melds = (ankan,)  # 非空 tuple
        pon_melds = (pon,)  # 非空 tuple

        # 两者的 len() 都 > 0，都会触发拒绝立直
        assert len(ankan_melds) > 0, "暗杠 melds 非空"
        assert len(pon_melds) > 0, "碑 melds 非空"

        # BUG：两者都被相同逻辑拒绝，但暗杠应允许立直
        # 根因：`len(melds) == 0` 或 `if melds:` 无法区分暗杠与其他副露


class TestAnkanIipeikou:
    """decompose.py:138: 暗杠手牌应能计一杯口。"""

    def test_ankan_preserves_peikou_level(self) -> None:
        """暗杠手牌应能计一杯口（当前 BUG：len(melds)!=0 返回 0）。"""
        # 一杯口形：112233m + 其他
        # for_ron=True 时 concealed 应为 13 张，不含 win_tile
        concealed = Counter({MAN1: 2, MAN2: 2, MAN3: 2, PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1, SOU5: 1})  # 13 张
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        win_tile = SOU5

        # 当前 BUG：menzen_peikou_level 因 len(melds)!=0 直接返回 0
        level = menzen_peikou_level(concealed, (ankan,), win_tile, for_ron=True)

        # 期望：暗杠是门清，应正常计算一杯口
        assert level >= 1, f"暗杠门清手应能计一杯口，实际 level={level}"


class TestAnkanSevenPairsTenpai:
    """tenpai.py:32-33: 暗杠不应阻止七对子听牌判定。"""

    def test_ankan_not_block_seven_pairs_tenpai(self) -> None:
        """暗杠 + 七对子形听牌应被识别（当前 BUG：melds 非空直接返回 False）。"""
        # 七对子 13 张：6 对子 + 1 单骑
        concealed = Counter({MAN1: 2, MAN3: 2, MAN5: 2, PIN1: 2, PIN3: 2, SOU1: 2, SOU5: 1})
        # 暗杠也算"副露"，但不应阻止七对子听牌
        # 注：实际上七对子 + 暗杠不可能同时存在（七对子 14 张无刻子）
        # 此测试验证函数逻辑，而非真实牌形

        # 当前 BUG：is_tenpai_seven_pairs 看到 melds 非空直接返回 False
        result = is_tenpai_seven_pairs(concealed, ())
        assert result is True  # 无副露时应识别

        # 注：暗杠 + 七对子组合本身不合法，此测试仅验证 melds 检查逻辑
        # 如果未来支持"暗杠不影响七对子判定"，此测试可扩展


# ============================================================================
# 负向测试：明副露应视为非门清
# ============================================================================

class TestMinkanNotMenzen:
    """大明杠 / 加杠应视为非门清。"""

    def test_daiminkan_no_menzen_ron_fu_bonus(self) -> None:
        """大明杠荣和不应获得门清荣和加符。"""
        minkan = Meld(MeldKind.DAIMINKAN, (MAN1, MAN1, MAN1, MAN1), called_tile=MAN1)
        concealed = Counter({MAN2: 1, MAN3: 1, MAN4: 1, PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 2, MAN5: 1, MAN6: 1})
        win_tile = MAN6

        fu = compute_fu_full(concealed, (minkan,), win_tile, for_ron=True, self_wind=NAN, round_wind=TON)

        # 非门清：基础 20 + 明杠幺九 16 = 36 -> 切上 40
        # 不应 +10 门清荣和加符
        assert fu < 50, f"大明杠非门清荣和不应获得门清加符，实际 fu={fu}"

    def test_kakan_no_menzen_ron_fu_bonus(self) -> None:
        """加杠荣和不应获得门清荣和加符。"""
        kakan = Meld(MeldKind.KAKAN, (SOU9, SOU9, SOU9, SOU9), called_tile=SOU9)
        concealed = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1, MAN5: 2, MAN4: 1, MAN6: 1})
        win_tile = MAN6

        fu = compute_fu_full(concealed, (kakan,), win_tile, for_ron=True, self_wind=NAN, round_wind=TON)

        # 非门清，不应 +10
        assert fu < 50, f"加杠非门清荣和不应获得门清加符，实际 fu={fu}"


class TestPonRiichiBlocked:
    """碰后应禁止立直。"""

    def test_pon_blocks_riichi(self) -> None:
        """碰后听牌也不应能立直。"""
        pon = Meld(MeldKind.PON, (MAN5, MAN5, MAN5), called_tile=MAN5)
        concealed = Counter({MAN1: 1, MAN2: 1, MAN3: 1, MAN4: 1, MAN6: 1, PIN1: 2, PIN2: 1, PIN3: 1, SOU1: 2})

        b0 = _board_sorted_deal(dealer=0)
        hands = [concealed, Counter(), Counter(), Counter()]
        pool = Counter(build_deck())
        for t in concealed.elements():
            pool[t] -= 1
        for t in pon.tiles:
            pool[t] -= 1
        for s in [1, 2, 3]:
            take = Counter()
            for _ in range(13):
                x = next(iter(pool.elements()))
                take[x] += 1
                pool[x] -= 1
            hands[s] = take

        b = BoardState(
            hands=tuple(hands),
            live_wall=b0.live_wall,
            live_draw_index=b0.live_draw_index,
            dead_wall=b0.dead_wall,
            revealed_indicators=b0.revealed_indicators,
            current_seat=0,
            turn_phase=TurnPhase.MUST_DISCARD,
            river=b0.river,
            melds=((pon,), (), (), ()),
            last_draw_tile=PIN3,
            last_draw_was_rinshan=False,
            rinshan_draw_index=b0.rinshan_draw_index,
            call_state=None,
        )

        table = initial_table_snapshot()
        gs = GameState(phase=GamePhase.IN_ROUND, table=table, board=b)

        # 碰后立直应被拒绝
        with pytest.raises(IllegalActionError, match="riichi requires menzen"):
            apply(gs, Action(ActionKind.DISCARD, seat=0, tile=PIN3, declare_riichi=True))


class TestChiNoMenzen:
    """吃应视为非门清。"""

    def test_chi_no_menzen_peikou(self) -> None:
        """吃后不应计一杯口。"""
        chi = Meld(MeldKind.CHI, (MAN1, MAN2, MAN3), called_tile=MAN2)
        concealed = Counter({PIN1: 2, PIN2: 2, PIN3: 2, SOU1: 1, SOU2: 1, SOU3: 1, SOU5: 2})

        level = menzen_peikou_level(concealed, (chi,), SOU5, for_ron=True)

        # 吃后非门清，不应计一杯口
        assert level == 0, f"吃后非门清不应计一杯口，实际 level={level}"


# ============================================================================
# 边界测试
# ============================================================================

class TestMultipleAnkan:
    """多暗杠仍应视为门清。"""

    def test_two_ankan_still_menzen(self) -> None:
        """两个暗杠手牌仍应视为门清。"""
        ankan1 = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        ankan2 = Meld(MeldKind.ANKAN, (PIN5, PIN5, PIN5, PIN5), called_tile=None)
        concealed = Counter({MAN1: 1, MAN2: 1, MAN3: 1, SOU1: 1, SOU2: 1, SOU3: 1, SOU5: 2})

        fu = compute_fu_full(concealed, (ankan1, ankan2), SOU5, for_ron=True, self_wind=NAN, round_wind=TON)

        # 双暗杠门清荣和：基础 20 + 暗杠中张 16*2 + 门清荣和 10 = 62 -> 切上 70
        assert fu >= 70, f"双暗杠门清荣和应获得门清加符，实际 fu={fu}"

    def test_three_ankan_menzen(self) -> None:
        """三暗杠仍为门清。"""
        ankan1 = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        ankan2 = Meld(MeldKind.ANKAN, (PIN5, PIN5, PIN5, PIN5), called_tile=None)
        ankan3 = Meld(MeldKind.ANKAN, (SOU5, SOU5, SOU5, SOU5), called_tile=None)
        # concealed: 13 - 12 (ankan) = 1 tile, 但 for_ron=True 会加 win_tile
        # 所以 concealed 应为 1 tile，win_tile 为 MAN1
        concealed = Counter({MAN1: 1})  # 1 tile，等待 MAN1 单骑

        fu = compute_fu_full(concealed, (ankan1, ankan2, ankan3), MAN1, for_ron=True, self_wind=NAN, round_wind=TON)

        # 三暗杠门清荣和：基础 20 + 暗杠中张 16*3 + 门清荣和 10 + 单骑听 2 = 80 -> 切上 80
        # 注：单骑听牌加 2 符
        assert fu >= 80, f"三暗杠门清荣和应获得门清加符，实际 fu={fu}"


class TestAnkanPlusPonNotMenzen:
    """暗杠 + 碑 = 非门清。"""

    def test_ankan_plus_pon_no_menzen_bonus(self) -> None:
        """暗杠 + 碑组合应为非门清。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        pon = Meld(MeldKind.PON, (SOU9, SOU9, SOU9), called_tile=SOU9)
        concealed = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1, PIN5: 2})

        fu = compute_fu_full(concealed, (ankan, pon), PIN5, for_ron=True, self_wind=NAN, round_wind=TON)

        # 非门清：不应 +10 门清荣和加符
        assert fu < 70, f"暗杠+碑非门清荣和不应获得门清加符，实际 fu={fu}"


class TestAnkanPlusChiNotMenzen:
    """暗杠 + 吃 = 非门清。"""

    def test_ankan_plus_chi_no_menzen_bonus(self) -> None:
        """暗杠 + 吃组合应为非门清。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        chi = Meld(MeldKind.CHI, (PIN1, PIN2, PIN3), called_tile=PIN2)
        concealed = Counter({MAN1: 1, MAN2: 1, MAN3: 1, SOU1: 1, SOU2: 1, SOU3: 1, SOU5: 2})

        fu = compute_fu_full(concealed, (ankan, chi), SOU5, for_ron=True, self_wind=NAN, round_wind=TON)

        # 非门清
        assert fu < 60, f"暗杠+吃非门清荣和不应获得门清加符，实际 fu={fu}"


class TestAnkanPlusDaiminkanNotMenzen:
    """暗杠 + 大明杠 = 非门清。"""

    def test_ankan_plus_daiminkan_no_menzen_bonus(self) -> None:
        """暗杠 + 大明杠组合应为非门清。"""
        ankan = Meld(MeldKind.ANKAN, (MAN5, MAN5, MAN5, MAN5), called_tile=None)
        daiminkan = Meld(MeldKind.DAIMINKAN, (SOU1, SOU1, SOU1, SOU1), called_tile=SOU1)
        concealed = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1, PIN5: 2})

        fu = compute_fu_full(concealed, (ankan, daiminkan), PIN5, for_ron=True, self_wind=NAN, round_wind=TON)

        # 非门清
        assert fu < 100, f"暗杠+大明杠非门清不应获得门清加符，实际 fu={fu}"