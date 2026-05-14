"""scoring.points 点棒计算测试。"""

from __future__ import annotations

from kernel.config import MahjongConfig
from kernel.scoring.points import (
    apply_kiriage_mangan,
    child_ron_base_points,
    child_ron_payment_from_discarder,
    child_tsumo_payments,
    dealer_ron_base_points,
    nagashi_mangan_payments,
    round_up_100,
)


# --- round_up_100 ---

class TestRoundUp100:
    def test_exact(self) -> None:
        assert round_up_100(8000) == 8000

    def test_round_up(self) -> None:
        assert round_up_100(8001) == 8100

    def test_round_up_boundary(self) -> None:
        assert round_up_100(7901) == 8000

    def test_zero(self) -> None:
        assert round_up_100(0) == 0

    def test_small(self) -> None:
        assert round_up_100(1) == 100


# --- apply_kiriage_mangan ---

class TestKiriageMangan:
    """切上满贯测试。"""

    def test_disabled_returns_base(self) -> None:
        cfg = MahjongConfig(kiriage_mangan_enabled=False)
        assert apply_kiriage_mangan(14100, 110, 3, cfg) == 14100

    def test_3han_60fu(self) -> None:
        """3番60符：基础点7700→切上满贯8000。"""
        cfg = MahjongConfig(kiriage_mangan_enabled=True)
        assert apply_kiriage_mangan(7700, 60, 3, cfg) == 8000

    def test_4han_30fu(self) -> None:
        """4番30符：基础点7700→切上满贯8000。"""
        cfg = MahjongConfig(kiriage_mangan_enabled=True)
        assert apply_kiriage_mangan(7700, 30, 4, cfg) == 8000

    def test_3han_59fu_no_trigger(self) -> None:
        """3番59符：基础点7500，不触发切上。"""
        cfg = MahjongConfig(kiriage_mangan_enabled=True)
        assert apply_kiriage_mangan(7500, 59, 3, cfg) == 7500

    def test_4han_29fu_no_trigger(self) -> None:
        """4番29符：基础点7400，不触发切上。"""
        cfg = MahjongConfig(kiriage_mangan_enabled=True)
        assert apply_kiriage_mangan(7400, 29, 4, cfg) == 7400

    def test_below_threshold(self) -> None:
        cfg = MahjongConfig(kiriage_mangan_enabled=True)
        # 3han 50fu: 不触发切上
        assert apply_kiriage_mangan(6500, 50, 3, cfg) == 6500

    def test_5han_no_effect(self) -> None:
        cfg = MahjongConfig(kiriage_mangan_enabled=True)
        # 5han 已是满贯，切上逻辑不影响
        assert apply_kiriage_mangan(8000, 30, 5, cfg) == 8000


# --- child_ron_base_points ---

class TestChildRonBasePoints:
    """子荣和基础点数。"""

    def test_mangan(self) -> None:
        assert child_ron_base_points(30, 5) == 8000

    def test_haneman(self) -> None:
        assert child_ron_base_points(30, 6) == 12000

    def test_baiman(self) -> None:
        assert child_ron_base_points(30, 8) == 16000

    def test_sanbaiman(self) -> None:
        assert child_ron_base_points(30, 11) == 24000

    def test_yakuman(self) -> None:
        assert child_ron_base_points(30, 13) == 32000

    def test_above_yakuman_cap(self) -> None:
        assert child_ron_base_points(30, 20) == 32000

    def test_raw_formula(self) -> None:
        # 4han 30fu: 30 * 4 * 2^6 = 7680 → 7700（禁用切上以验证原始公式）
        cfg = MahjongConfig(kiriage_mangan_enabled=False)
        assert child_ron_base_points(30, 4, cfg) == 7700

    def test_kiriage_applies(self) -> None:
        # 3han 110fu: 切上满贯 → 8000
        assert child_ron_base_points(110, 3) == 8000

    def test_kiriage_disabled(self) -> None:
        cfg = MahjongConfig(kiriage_mangan_enabled=False)
        # 3han 110fu: 110 * 4 * 32 = 14080 → 14100
        assert child_ron_base_points(110, 3, cfg) == 14100


# --- dealer_ron_base_points ---

class TestDealerRonBasePoints:
    """亲荣和基础点数。"""

    def test_mangan(self) -> None:
        assert dealer_ron_base_points(30, 5) == 12000

    def test_haneman(self) -> None:
        assert dealer_ron_base_points(30, 6) == 18000

    def test_baiman(self) -> None:
        assert dealer_ron_base_points(30, 8) == 24000

    def test_sanbaiman(self) -> None:
        assert dealer_ron_base_points(30, 11) == 36000

    def test_yakuman(self) -> None:
        assert dealer_ron_base_points(30, 13) == 48000

    def test_above_yakuman_cap(self) -> None:
        assert dealer_ron_base_points(30, 20) == 48000

    def test_raw_formula(self) -> None:
        # 4han 30fu: 30 * 6 * 2^6 = 11520 → 11600
        assert dealer_ron_base_points(30, 4) == 11600


# --- child_ron_payment_from_discarder ---

class TestRonPayment:
    """荣和支付（含本场）。"""

    def test_child_win_no_honba(self) -> None:
        # 子赢 4han 30fu: 切上满贯 8000 + 0
        assert child_ron_payment_from_discarder(
            winner=1, discarder=2, dealer=0, fu=30, han=4, honba=0
        ) == 8000

    def test_child_win_with_honba(self) -> None:
        # 子赢 4han 30fu, 2本场: 切上满贯 8000 + 600
        assert child_ron_payment_from_discarder(
            winner=1, discarder=2, dealer=0, fu=30, han=4, honba=2
        ) == 8600

    def test_dealer_win_no_honba(self) -> None:
        # 亲赢 4han 30fu: 11600 + 0
        assert child_ron_payment_from_discarder(
            winner=0, discarder=2, dealer=0, fu=30, han=4, honba=0
        ) == 11600

    def test_dealer_win_with_honba(self) -> None:
        # 亲赢 4han 30fu, 3本场: 11600 + 900
        assert child_ron_payment_from_discarder(
            winner=0, discarder=2, dealer=0, fu=30, han=4, honba=3
        ) == 12500


# --- child_tsumo_payments ---

class TestTsumoPayments:
    """自摸支付。"""

    def test_child_win_no_honba(self) -> None:
        # 子赢 4han 30fu: 子付 2000, 亲付 3900 (→ 4000)
        # _tsumo_from_child_non_dealer(30,4) = round_up(30*64) = 2000
        # _tsumo_from_dealer_when_child_wins(30,4) = round_up(60*64) = 3900 → 3900
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=4, honba=0)
        assert sum(p.values()) == 0  # 收支平衡
        assert p[1] > 0  # 赢家收入
        assert p[0] < 0  # 亲家支付
        assert p[2] < 0  # 子家支付

    def test_dealer_win_no_honba(self) -> None:
        # 亲赢 5han 30fu: 每家付 4000
        p = child_tsumo_payments(winner=0, dealer=0, fu=30, han=5, honba=0)
        assert sum(p.values()) == 0
        assert p[0] == 12000
        assert p[1] == -4000
        assert p[2] == -4000
        assert p[3] == -4000

    def test_child_win_with_honba(self) -> None:
        # 子赢 5han, 2本场: 每名支付者 +200
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=5, honba=2)
        assert sum(p.values()) == 0
        # 子付: 2000 + 200 = 2200
        assert p[2] == -2200
        # 亲付: 4000 + 200 = 4200
        assert p[0] == -4200

    def test_dealer_win_with_honba(self) -> None:
        # 亲赢 5han, 1本场: 每家付 4000 + 100 = 4100
        p = child_tsumo_payments(winner=0, dealer=0, fu=30, han=5, honba=1)
        assert sum(p.values()) == 0
        assert p[1] == -4100
        assert p[0] == 12300

    def test_yakuman_child(self) -> None:
        # 子赢 yakuman: 子付 8000, 亲付 16000
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=13, honba=0)
        assert p[1] == 32000  # 8000*2 + 16000
        assert p[0] == -16000
        assert p[2] == -8000
        assert p[3] == -8000

    def test_yakuman_dealer(self) -> None:
        # 亲赢 yakuman: 每家付 16000
        p = child_tsumo_payments(winner=0, dealer=0, fu=30, han=13, honba=0)
        assert p[0] == 48000
        assert p[1] == -16000
        assert p[2] == -16000
        assert p[3] == -16000

    def test_child_mangan(self) -> None:
        # 子赢 5han: 子付 2000, 亲付 4000
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=5, honba=0)
        assert p[2] == -2000
        assert p[0] == -4000
        assert p[1] == 8000

    def test_child_haneman(self) -> None:
        # 子赢 6han: 子付 3000, 亲付 6000
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=6, honba=0)
        assert p[2] == -3000
        assert p[0] == -6000
        assert p[1] == 12000

    def test_child_baiman(self) -> None:
        # 子赢 8han: 子付 4000, 亲付 8000
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=8, honba=0)
        assert p[2] == -4000
        assert p[0] == -8000
        assert p[1] == 16000

    def test_child_sanbaiman(self) -> None:
        # 子赢 11han: 子付 6000, 亲付 12000
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=11, honba=0)
        assert p[2] == -6000
        assert p[0] == -12000
        assert p[1] == 24000

    def test_dealer_haneman(self) -> None:
        # 亲赢 6han: 每家付 6000
        p = child_tsumo_payments(winner=0, dealer=0, fu=30, han=6, honba=0)
        assert p[1] == -6000
        assert p[0] == 18000

    def test_dealer_baiman(self) -> None:
        # 亲赢 8han: 每家付 8000
        p = child_tsumo_payments(winner=0, dealer=0, fu=30, han=8, honba=0)
        assert p[1] == -8000
        assert p[0] == 24000

    def test_dealer_sanbaiman(self) -> None:
        # 亲赢 11han: 每家付 12000
        p = child_tsumo_payments(winner=0, dealer=0, fu=30, han=11, honba=0)
        assert p[1] == -12000
        assert p[0] == 36000

    def test_raw_formula_child(self) -> None:
        # 子赢 4han 30fu: 子付 round_up(30*64)=2000, 亲付 round_up(60*64)=3900
        p = child_tsumo_payments(winner=1, dealer=0, fu=30, han=4, honba=0)
        assert p[2] == -2000
        assert p[0] == -3900
        assert p[1] == 7900

    def test_raw_formula_dealer(self) -> None:
        # 亲赢 4han 30fu: 每家付 round_up(30*64)=2000
        p = child_tsumo_payments(winner=0, dealer=0, fu=30, han=4, honba=0)
        assert p[1] == -2000
        assert p[0] == 6000


# --- nagashi_mangan_payments ---

class TestNagashiManganPayments:
    """流し満貫支付。"""

    def test_all_noten_child_win(self) -> None:
        # 子赢，三家未听: 等价于 5han 30fu 自摸
        noten = frozenset({0, 2, 3})
        p = nagashi_mangan_payments(winner=1, dealer=0, honba=0, noten=noten)
        ref = child_tsumo_payments(winner=1, dealer=0, fu=30, han=5, honba=0)
        assert p == ref

    def test_all_noten_dealer_win(self) -> None:
        # 亲赢，三家未听
        noten = frozenset({1, 2, 3})
        p = nagashi_mangan_payments(winner=0, dealer=0, honba=0, noten=noten)
        ref = child_tsumo_payments(winner=0, dealer=0, fu=30, han=5, honba=0)
        assert p == ref

    def test_no_payers(self) -> None:
        # 所有人听牌，无人支付
        noten = frozenset()
        p = nagashi_mangan_payments(winner=1, dealer=0, honba=0, noten=noten)
        assert p == {0: 0, 1: 0, 2: 0, 3: 0}

    def test_partial_payers(self) -> None:
        # 只有部分人未听: 按比例缩放
        noten = frozenset({0, 2})  # 亲和子2未听，子3听牌
        p = nagashi_mangan_payments(winner=1, dealer=0, honba=0, noten=noten)
        # 总额不变: 子赢应得 8000 (满贯自摸总额)
        assert p[1] > 0
        assert sum(p.values()) == 0

    def test_with_honba(self) -> None:
        noten = frozenset({0, 2, 3})
        p = nagashi_mangan_payments(winner=1, dealer=0, honba=2, noten=noten)
        ref = child_tsumo_payments(winner=1, dealer=0, fu=30, han=5, honba=2)
        assert p == ref
