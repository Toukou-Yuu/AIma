"""番符→点棒（子家/亲、荣和、自摸）；满贯阶梯与切上。"""

from __future__ import annotations

from kernel.config import get_default_config, MahjongConfig


def round_up_100(x: int) -> int:
    return (x + 99) // 100 * 100


def apply_kiriage_mangan(
    base: int,
    fu: int,
    han: int,
    config: MahjongConfig | None = None,
) -> int:
    """
    切上满贯适用：子家基础点经百切后落在 [7700, 7900] 时切上为满贯 8000。

    典型场景：3 番 60 符 = 7680 → 7700，4 番 30 符 = 7680 → 7700。
    仅处理子家边界情况，满贯阶梯封顶和亲家切上由调用方负责。
    """
    config = config or get_default_config()
    if not config.kiriage_mangan_enabled:
        return base
    if 7700 <= base <= 7900:
        return 8000
    return base


def child_ron_base_points(fu: int, han: int, config: MahjongConfig | None = None) -> int:
    """子荣和：点棒公式 ``fu * 4 * 2^(2+han)`` 再切上，受满贯阶梯限制。"""
    config = config or get_default_config()
    if han >= 13:
        return 32_000
    if han >= 11:
        return 24_000
    if han >= 8:
        return 16_000
    if han >= 6:
        return 12_000
    if han >= 5:
        return 8_000
    raw = fu * 4 * (2 ** (2 + han))
    base = round_up_100(raw)
    base = apply_kiriage_mangan(base, fu, han, config)
    if config.kiriage_mangan_enabled and base > 8000:
        return 8000
    return base


def dealer_ron_base_points(fu: int, han: int, config: MahjongConfig | None = None) -> int:
    """亲荣和（子点亲）：``fu * 6 * 2^(2+han)`` 系，阶梯同量级按常见表取整。"""
    config = config or get_default_config()
    if han >= 13:
        return 48_000
    if han >= 11:
        return 36_000
    if han >= 8:
        return 24_000
    if han >= 6:
        return 18_000
    if han >= 5:
        return 12_000
    raw = fu * 6 * (2 ** (2 + han))
    base = round_up_100(raw)
    base = apply_kiriage_mangan(base, fu, han, config)
    if config.kiriage_mangan_enabled and base > 12000:
        return 12000
    return base


def child_ron_payment_from_discarder(
    winner: int,
    discarder: int,
    dealer: int,
    fu: int,
    han: int,
    honba: int,
    config: MahjongConfig | None = None,
) -> int:
    """单家和了者从放铳家应收点数（含本场 300/本）。"""
    config = config or get_default_config()
    is_dealer_win = winner == dealer
    if is_dealer_win:
        base = dealer_ron_base_points(fu, han, config)
    else:
        base = child_ron_base_points(fu, han, config)
    return base + config.honba_value * honba


def _tsumo_from_child_non_dealer(fu: int, han: int) -> int:
    """子家和了自摸时：另一子家应付的基础（未含本场）。"""
    if han >= 13:
        return 8_000
    if han >= 11:
        return 6_000
    if han >= 8:
        return 4_000
    if han >= 6:
        return 3_000
    if han >= 5:
        return 2_000
    return round_up_100(fu * (2 ** (2 + han)))


def _tsumo_from_dealer_when_child_wins(fu: int, han: int) -> int:
    """子家和了自摸时：亲家应付的基础（未含本场）。"""
    if han >= 13:
        return 16_000
    if han >= 11:
        return 12_000
    if han >= 8:
        return 8_000
    if han >= 6:
        return 6_000
    if han >= 5:
        return 4_000
    return round_up_100(2 * fu * (2 ** (2 + han)))


def _tsumo_each_pays_dealer_win(fu: int, han: int) -> int:
    """亲自摸时三家子各付（未含本场）。"""
    if han >= 13:
        return 16_000
    if han >= 11:
        return 12_000
    if han >= 8:
        return 8_000
    if han >= 6:
        return 6_000
    if han >= 5:
        return 4_000
    return round_up_100(fu * (2 ** (2 + han)))


def child_tsumo_payments(
    winner: int,
    dealer: int,
    fu: int,
    han: int,
    honba: int,
) -> dict[int, int]:
    """
    自摸支付：返回各席点棒增量（负为支付、正为收入）。
    本场：每名支付者另加 ``100 * honba``。
    """
    out = {0: 0, 1: 0, 2: 0, 3: 0}
    hb = 100 * honba
    if winner == dealer:
        each = _tsumo_each_pays_dealer_win(fu, han) + hb
        for s in range(4):
            if s == winner:
                continue
            out[s] -= each
            out[winner] += each
        return out
    from_child = _tsumo_from_child_non_dealer(fu, han) + hb
    from_dealer = _tsumo_from_dealer_when_child_wins(fu, han) + hb
    for s in range(4):
        if s == winner:
            continue
        pay = from_dealer if s == dealer else from_child
        out[s] -= pay
        out[winner] += pay
    return out


def nagashi_mangan_payments(
    winner: int,
    dealer: int,
    honba: int,
    noten: frozenset[int],
) -> dict[int, int]:
    """
    流し満貫（荒牌流局）：与**满贯自摸**同一总额，按亲/子分摊至未听者。

    - 子家和了：合计 **8000**（+ 本场每名 100×honba）= 亲付 **4000**、另两家子各 **2000**（+本场）
    - 亲家和了：合计 **12000**（+本场）= 三家子各 **4000**（+本场）

    并非「每家未听者各付 8000/12000」。

    未听者恰为三家时，与 ``child_tsumo_payments(..., fu=30, han=5, honba)`` 完全一致。
    未听者少于三家时，按满额自摸下各非和了者应付额之比例，在仅未听者之间缩放到总额不变。
    """
    full = child_tsumo_payments(winner, dealer, 30, 5, honba)
    target = full[winner]
    losses = {s: -full[s] for s in range(4) if s != winner}
    payers = sorted(s for s in range(4) if s != winner and s in noten)
    if not payers:
        return {0: 0, 1: 0, 2: 0, 3: 0}
    if frozenset(payers) == frozenset(losses.keys()):
        return full
    sum_raw = sum(losses[s] for s in payers)
    out = {0: 0, 1: 0, 2: 0, 3: 0}
    if sum_raw <= 0:
        each = target // len(payers)
        for n in payers:
            out[n] -= each
        out[winner] = -sum(out[s] for s in range(4))
        return out
    remainder = target
    for n in payers[:-1]:
        pay = (losses[n] * target + sum_raw // 2) // sum_raw
        out[n] -= pay
        remainder -= pay
    out[payers[-1]] -= remainder
    out[winner] = target
    return out
