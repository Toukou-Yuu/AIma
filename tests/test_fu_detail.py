"""scoring.fu 符计算详细测试。"""

from __future__ import annotations

from collections import Counter

from kernel.hand.melds import Meld, MeldKind
from kernel.scoring.fu import (
    compute_fu,
    compute_fu_detail,
    compute_fu_full,
    compute_fu_simple,
)
from kernel.tiles.model import Suit, Tile

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
TON = Tile(Suit.HONOR, 1)  # 东
NAN = Tile(Suit.HONOR, 2)  # 南
SHA = Tile(Suit.HONOR, 3)  # 西
PEI = Tile(Suit.HONOR, 4)  # 北


# --- compute_fu_detail ---

class TestFuDetailChiitoitsu:
    """七对子固定 25 符。"""

    def test_chiitoitsu(self) -> None:
        c = Counter({MAN1: 2, MAN3: 2, MAN5: 2, MAN7: 2, PIN1: 2, PIN3: 2, SOU1: 2})
        d = compute_fu_detail(c, (), MAN1, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON, is_chiitoitsu=True)
        assert d["total"] == 25
        assert d["base"] == 25
        assert d["tsumo"] == 0


class TestFuDetailPinfu:
    """平和符。"""

    def test_pinfu_ron(self) -> None:
        # 平和荣和: 20 + 10 = 30
        c = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN4: 1, PIN5: 1, PIN6: 1,
                     SOU7: 1, SOU8: 1, SOU9: 1, MAN5: 2, PIN1: 1, PIN2: 1})
        d = compute_fu_detail(c, (), PIN3, for_ron=True, menzen=True, pinfu=True,
                              self_wind=NAN, round_wind=TON)
        assert d["total"] == 30

    def test_pinfu_tsumo(self) -> None:
        # 平和自摸: 20 符（不加自摸符）
        c = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN4: 1, PIN5: 1, PIN6: 1,
                     SOU7: 1, SOU8: 1, SOU9: 1, MAN5: 2, PIN1: 1, PIN2: 1})
        d = compute_fu_detail(c, (), PIN3, for_ron=False, menzen=True, pinfu=True,
                              self_wind=NAN, round_wind=TON)
        assert d["total"] == 20


class TestFuDetailNonPinfu:
    """非平和符分解。"""

    def test_base_plus_tsumo(self) -> None:
        # 非平和自摸: 20 + 2 = 22 → 30（切上）
        c = Counter({MAN1: 2, MAN2: 1, MAN3: 1, MAN4: 1, PIN1: 2, PIN2: 1, PIN3: 1,
                     PIN4: 1, SOU1: 2})
        d = compute_fu_detail(c, (), SOU1, for_ron=False, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["base"] == 20
        assert d["tsumo"] == 2
        assert d["menzen_ron"] == 0

    def test_menzen_ron_bonus(self) -> None:
        # 门清荣和: +10
        c = Counter({MAN1: 2, MAN2: 1, MAN3: 1, MAN4: 1, PIN1: 2, PIN2: 1, PIN3: 1,
                     PIN4: 1, SOU1: 2})
        d = compute_fu_detail(c, (), SOU1, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["menzen_ron"] == 10

    def test_pair_fu_yakuhai_dragon(self) -> None:
        # 三元牌对子: +2
        c = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1,
                     SOU1: 1, SOU2: 1, SOU3: 1, HAKU: 2, MAN4: 1, MAN5: 1})
        d = compute_fu_detail(c, (), MAN6, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["pair"] == 2

    def test_pair_fu_round_wind(self) -> None:
        # 场风对子: +2
        c = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1,
                     SOU1: 1, SOU2: 1, SOU3: 1, TON: 2, MAN4: 1, MAN5: 1})
        d = compute_fu_detail(c, (), MAN6, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["pair"] == 2

    def test_pair_fu_self_wind(self) -> None:
        # 自风对子: +2
        c = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1,
                     SOU1: 1, SOU2: 1, SOU3: 1, NAN: 2, MAN4: 1, MAN5: 1})
        d = compute_fu_detail(c, (), MAN6, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["pair"] == 2

    def test_pair_fu_double_wind(self) -> None:
        # 场风==自风时计 4 符（雀魂规则：双计）
        c = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1,
                     SOU1: 1, SOU2: 1, SOU3: 1, TON: 2, MAN4: 1, MAN5: 1})
        d = compute_fu_detail(c, (), MAN6, for_ron=True, menzen=True, pinfu=False,
                              self_wind=TON, round_wind=TON)
        assert d["pair"] == 4  # 连风雀头：场风2符 + 自风2符

    def test_pair_fu_non_yakuhai(self) -> None:
        # 非役牌对子: 0
        c = Counter({MAN1: 1, MAN2: 1, MAN3: 1, PIN1: 1, PIN2: 1, PIN3: 1,
                     SOU1: 1, SOU2: 1, SOU3: 1, MAN5: 2, MAN4: 1, PIN4: 1})
        d = compute_fu_detail(c, (), PIN5, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["pair"] == 0

    def test_set_fu_anko_middle(self) -> None:
        # 暗刻中张: +4
        c = Counter({MAN5: 3, PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN1: 2, MAN2: 1, MAN3: 1})
        d = compute_fu_detail(c, (), MAN4, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["sets"] >= 4

    def test_set_fu_anko_terminal(self) -> None:
        # 暗刻幺九: +8
        c = Counter({MAN1: 3, PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN5: 2, MAN2: 1, MAN3: 1})
        d = compute_fu_detail(c, (), MAN4, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["sets"] >= 8

    def test_set_fu_with_pon(self) -> None:
        # 明刻（碰）中张: +2 符
        pon_meld = Meld(kind=MeldKind.PON, tiles=(MAN5, MAN5, MAN5), called_tile=MAN5)
        c = Counter({PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN1: 2, MAN2: 1, MAN3: 1, MAN4: 1})
        d = compute_fu_detail(c, (pon_meld,), MAN4, for_ron=True, menzen=False, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        # 明刻中张 5m: +2 符
        assert d["sets"] >= 2

    def test_set_fu_with_pon_terminal(self) -> None:
        # 明刻（碰）幺九字牌: +4 符
        pon_meld = Meld(kind=MeldKind.PON, tiles=(MAN1, MAN1, MAN1), called_tile=MAN1)
        c = Counter({PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN5: 2, MAN2: 1, MAN3: 1, MAN4: 1})
        d = compute_fu_detail(c, (pon_meld,), MAN4, for_ron=True, menzen=False, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        # 明刻幺九 1m: +4 符
        assert d["sets"] >= 4

    def test_set_fu_with_ankan(self) -> None:
        # 暗杠中张: +16
        ankan_meld = Meld(kind=MeldKind.ANKAN, tiles=(MAN5, MAN5, MAN5, MAN5), called_tile=None)
        c = Counter({PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN1: 2, MAN2: 1, MAN3: 1})
        d = compute_fu_detail(c, (ankan_meld,), MAN4, for_ron=True, menzen=False, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["sets"] >= 16

    def test_set_fu_with_minkan(self) -> None:
        # 明杠幺九: +16
        minkan_meld = Meld(kind=MeldKind.DAIMINKAN, tiles=(MAN1, MAN1, MAN1, MAN1),
                           called_tile=MAN1)
        c = Counter({PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN5: 2, MAN2: 1, MAN3: 1, MAN4: 1})
        d = compute_fu_detail(c, (minkan_meld,), MAN4, for_ron=True, menzen=False, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["sets"] >= 16

    def test_set_fu_with_kakan(self) -> None:
        # 加杠视为明杠
        kakan_meld = Meld(kind=MeldKind.KAKAN, tiles=(SOU9, SOU9, SOU9, SOU9),
                            called_tile=SOU9)
        c = Counter({PIN1: 1, PIN2: 1, PIN3: 1, MAN1: 1, MAN2: 1, MAN3: 1,
                     MAN5: 2, MAN4: 1, MAN6: 1})
        d = compute_fu_detail(c, (kakan_meld,), MAN7, for_ron=True, menzen=False, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        # kakan 终末牌: +16
        assert d["sets"] >= 16

    def test_total_rounding(self) -> None:
        # 总符切上到 10 的倍数
        c = Counter({MAN1: 3, PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN5: 2, MAN2: 1, MAN3: 1})
        d = compute_fu_detail(c, (), MAN4, for_ron=False, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["total"] % 10 == 0


class TestFuDetailWaitType:
    """听牌类型加符（+2）：嵌张/单骑/边张。"""

    def test_kanchan_wait(self) -> None:
        """嵌张听（1_3 听 2）: +2 符。"""
        # 13 tiles: 1m 3m + 5m5m + 1p2p3p + 4p5p6p + 7p8p9p wait 2m
        c = Counter({MAN1: 1, MAN3: 1, MAN5: 2, PIN1: 1, PIN2: 1, PIN3: 1,
                     PIN4: 1, PIN5: 1, PIN6: 1, PIN7: 1, PIN8: 1, PIN9: 1})
        d = compute_fu_detail(c, (), MAN2, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["wait"] == 2

    def test_tanki_wait(self) -> None:
        """单骑听（对子听第 3 张）: +2 符。"""
        # 13 tiles: 5s + 1p2p3p + 4p5p6p + 7p8p9p + 1s2s3s wait 5s
        c = Counter({SOU5: 1, PIN1: 1, PIN2: 1, PIN3: 1, PIN4: 1, PIN5: 1, PIN6: 1,
                     PIN7: 1, PIN8: 1, PIN9: 1, SOU1: 1, SOU2: 1, SOU3: 1})
        d = compute_fu_detail(c, (), SOU5, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["wait"] == 2

    def test_penchan_wait(self) -> None:
        """边张听（12 听 3）: +2 符。"""
        # 13 tiles: 1m 2m + 5m5m + 1p2p3p + 4p5p6p + 7p8p9p wait 3m
        c = Counter({MAN1: 1, MAN2: 1, MAN5: 2, PIN1: 1, PIN2: 1, PIN3: 1,
                     PIN4: 1, PIN5: 1, PIN6: 1, PIN7: 1, PIN8: 1, PIN9: 1})
        d = compute_fu_detail(c, (), MAN3, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d["wait"] == 2

    def test_ryanmen_no_wait_fu(self) -> None:
        """两面听不加符。"""
        # 2m3m 等 4m（两面听）: 不加符
        c = Counter({MAN2: 1, MAN3: 1, MAN5: 2, PIN1: 1, PIN2: 1, PIN3: 1,
                     PIN4: 1, PIN5: 1, PIN6: 1, PIN7: 1, PIN8: 1, PIN9: 1})
        d = compute_fu_detail(c, (), MAN4, for_ron=True, menzen=True, pinfu=False,
                              self_wind=NAN, round_wind=TON)
        assert d.get("wait", 0) == 0


# --- compute_fu (simplified) ---

class TestComputeFu:
    def test_pinfu_ron(self) -> None:
        assert compute_fu(menzen=True, is_ron=True, pinfu=True) == 30

    def test_pinfu_tsumo(self) -> None:
        assert compute_fu(menzen=True, is_ron=False, pinfu=True) == 20

    def test_non_pinfu_menzen_ron(self) -> None:
        assert compute_fu(menzen=True, is_ron=True, pinfu=False) == 40

    def test_non_pinfu_open_ron(self) -> None:
        assert compute_fu(menzen=False, is_ron=True, pinfu=False) == 30

    def test_non_pinfu_tsumo(self) -> None:
        assert compute_fu(menzen=True, is_ron=False, pinfu=False) == 40

    def test_simple(self) -> None:
        assert compute_fu_simple(menzen=True, is_ron=True) == 40


# --- compute_fu_full ---

class TestComputeFuFull:
    def test_pinfu_ron(self) -> None:
        # 平和荣和: 30 符（两面听：2m3m 等 1m 或 4m）
        c = Counter({MAN2: 1, MAN3: 1, PIN4: 1, PIN5: 1, PIN6: 1,
                     SOU7: 1, SOU8: 1, SOU9: 1, MAN5: 2, PIN1: 1, PIN2: 1, PIN3: 1})
        assert compute_fu_full(c, (), MAN1, for_ron=True,
                               self_wind=NAN, round_wind=TON) == 30

    def test_non_pinfu(self) -> None:
        # 有暗刻的非平和手
        c = Counter({MAN1: 3, PIN1: 1, PIN2: 1, PIN3: 1, SOU1: 1, SOU2: 1, SOU3: 1,
                     MAN5: 2, MAN2: 1, MAN3: 1})
        fu = compute_fu_full(c, (), MAN4, for_ron=True,
                             self_wind=NAN, round_wind=TON)
        assert fu >= 40
        assert fu % 10 == 0

    def test_chiitoitsu(self) -> None:
        """七对子通过 compute_fu_full 应返回 25 符。"""
        # 13 张门内：6 对 + 1 张单张（MAN1），荣和 MAN1 凑成第 7 对
        c = Counter({MAN1: 1, MAN3: 2, MAN5: 2, MAN7: 2, PIN1: 2, PIN3: 2, SOU1: 2})
        assert compute_fu_full(c, (), MAN1, for_ron=True,
                               self_wind=NAN, round_wind=TON) == 25
