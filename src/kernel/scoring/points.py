"""番符→点棒（子家/亲、荣和、自摸）；满贯阶梯与切上。"""

from __future__ import annotations


def round_up_100(x: int) -> int:
    return (x + 99) // 100 * 100


def child_ron_base_points(fu: int, han: int) -> int:
    """子荣和：点棒公式 ``fu * 4 * 2^(2+han)`` 再切上，受满贯阶梯限制。"""
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
    return round_up_100(raw)


def dealer_ron_base_points(fu: int, han: int) -> int:
    """亲荣和（子点亲）：``fu * 6 * 2^(2+han)`` 系，阶梯同量级按常见表取整。"""
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
    return round_up_100(raw)


def child_ron_payment_from_discarder(
    winner: int,
    discarder: int,
    dealer: int,
    fu: int,
    han: int,
    honba: int,
) -> int:
    """单家和了者从放铳家应收点数（含本场 300/本）。"""
    is_dealer_win = winner == dealer
    if is_dealer_win:
        base = dealer_ron_base_points(fu, han)
    else:
        base = child_ron_base_points(fu, han)
    return base + 300 * honba


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
