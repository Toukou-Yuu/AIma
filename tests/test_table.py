"""Tests for table / round context snapshot."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kernel import (
    MatchPreset,
    PrevailingWind,
    RoundNumber,
    TableSnapshot,
    initial_table_snapshot,
    seat_wind_rank,
)


def test_initial_table_snapshot_defaults() -> None:
    s = initial_table_snapshot()
    assert s.prevailing_wind == PrevailingWind.EAST
    assert s.round_number == RoundNumber.ONE
    assert s.dealer_seat == 0
    assert s.honba == 0
    assert s.kyoutaku == 0
    assert s.scores == (25_000, 25_000, 25_000, 25_000)
    assert s.match_preset == MatchPreset.HANCHAN


def test_initial_table_snapshot_dealer_and_points() -> None:
    s = initial_table_snapshot(dealer_seat=2, starting_points=30_000)
    assert s.dealer_seat == 2
    assert s.scores == (30_000, 30_000, 30_000, 30_000)


def test_initial_table_snapshot_negative_starting_raises() -> None:
    with pytest.raises(ValueError, match="starting_points"):
        initial_table_snapshot(starting_points=-1)


def test_seat_wind_rank_dealer_zero() -> None:
    d = 0
    assert seat_wind_rank(d, 0) == 1  # 东
    assert seat_wind_rank(d, 1) == 2  # 南
    assert seat_wind_rank(d, 2) == 3  # 西
    assert seat_wind_rank(d, 3) == 4  # 北


def test_seat_wind_rank_dealer_one() -> None:
    d = 1
    assert seat_wind_rank(d, 1) == 1
    assert seat_wind_rank(d, 2) == 2
    assert seat_wind_rank(d, 3) == 3
    assert seat_wind_rank(d, 0) == 4


def test_seat_wind_rank_invalid_seat_raises() -> None:
    with pytest.raises(ValueError, match="seat"):
        seat_wind_rank(0, 4)


def test_seat_wind_rank_invalid_dealer_raises() -> None:
    with pytest.raises(ValueError, match="dealer_seat"):
        seat_wind_rank(4, 0)


def test_table_snapshot_invalid_dealer_on_construct_raises() -> None:
    base = initial_table_snapshot()
    with pytest.raises(ValueError, match="dealer_seat"):
        replace(base, dealer_seat=5)


def test_table_snapshot_negative_honba_raises() -> None:
    base = initial_table_snapshot()
    with pytest.raises(ValueError, match="honba"):
        replace(base, honba=-1)


def test_table_snapshot_scores_wrong_length_raises() -> None:
    base = initial_table_snapshot()
    with pytest.raises(ValueError, match="length 4"):
        replace(base, scores=(1, 2, 3))


def test_table_snapshot_negative_score_allowed() -> None:
    """负分现在允许（结算后可能出现负分，通过 clamp_scores 钳位）。"""
    base = initial_table_snapshot()
    from dataclasses import replace
    # 负分不再抛异常
    negative_table = replace(base, scores=(-1, 0, 0, 0))
    assert negative_table.scores == (-1, 0, 0, 0)


def test_clamp_scores_basic() -> None:
    """clamp_scores 将负分钳位到 0。"""
    from kernel.table.model import clamp_scores
    assert clamp_scores((-100, 0, 500, -50)) == (0, 0, 500, 0)
    assert clamp_scores((100, 200, 300, 400)) == (100, 200, 300, 400)
    assert clamp_scores((0, 0, 0, 0)) == (0, 0, 0, 0)


def test_nonzero_honba_kyoutaku_valid() -> None:
    s = initial_table_snapshot(honba=2, kyoutaku=3000)
    assert s.honba == 2
    assert s.kyoutaku == 3000
    assert isinstance(s, TableSnapshot)


def test_tonpuu_preset() -> None:
    s = initial_table_snapshot(match_preset=MatchPreset.TONPUSEN)
    assert s.match_preset == MatchPreset.TONPUSEN


def test_initial_table_snapshot_starting_dealer_seat() -> None:
    """starting_dealer_seat 默认为 dealer_seat，可单独指定。"""
    s = initial_table_snapshot()
    assert s.starting_dealer_seat == 0
    assert s.dealer_seat == 0

    # 单独指定起家
    s2 = initial_table_snapshot(dealer_seat=2, starting_dealer_seat=0)
    assert s2.dealer_seat == 2
    assert s2.starting_dealer_seat == 0


def test_compute_match_ranking_tiebreak_by_starting_dealer() -> None:
    """同分时按起家顺序排列：起家优先（距起家越近排名越高）。

    注意：同分者仍然并列排名，tie-break 仅影响排序顺序（用于供托分配）。
    """
    from kernel.table.transitions import compute_match_ranking

    # 起家 = 0，三家同分
    table = initial_table_snapshot(
        starting_points=25000,
        starting_dealer_seat=0,
    )
    # 调整分数：三家同分 30000，一家 20000
    table = replace(
        table,
        scores=(30000, 30000, 30000, 20000),
    )
    ranking = compute_match_ranking(table)
    # 同分者并列：三家并列 1 位，第 4 家是 4 位
    assert ranking == (1, 1, 1, 4)

    # 起家 = 2，三家同分（seat 0, 2, 3）
    # 分数：seat 0=30000, seat 1=25000, seat 2=30000, seat 3=30000
    table = replace(
        initial_table_snapshot(starting_dealer_seat=2),
        scores=(30000, 25000, 30000, 30000),
    )
    ranking = compute_match_ranking(table)
    # 同分者并列 1 位：seat 0, 2, 3
    # 排序顺序（距离升序）：seat 2(0) → seat 3(1) → seat 0(2)
    assert ranking == (1, 4, 1, 1)


def test_final_settlement_kyoutaku_remainder_distribution() -> None:
    """供托余数按座位顺序依次分配，保持点棒守恒。

    注意：同分者并列排名，但供托分配按排序顺序（起家优先）。
    """
    from kernel.table.transitions import final_settlement

    # 两家并列 1 位，供托 3000（均分 1500/1500，无余数）
    table = replace(
        initial_table_snapshot(starting_dealer_seat=0),
        scores=(30000, 30000, 25000, 15000),
        kyoutaku=3000,
    )
    ranking, new_table = final_settlement(table)
    # 同分者并列 1 位
    assert ranking == (1, 1, 3, 4)
    assert new_table.kyoutaku == 0
    assert new_table.scores[0] == 31500  # +1500
    assert new_table.scores[1] == 31500  # +1500

    # 两家并列 1 位，供托 2500（均分 1250/1250，余数 0 → 无余数）
    table = replace(
        initial_table_snapshot(starting_dealer_seat=0),
        scores=(30000, 30000, 25000, 15000),
        kyoutaku=2500,
    )
    ranking, new_table = final_settlement(table)
    assert new_table.scores[0] == 30000 + 1250  # +1250
    assert new_table.scores[1] == 30000 + 1250  # +1250
    # 验证点棒守恒
    total_before = sum(table.scores) + table.kyoutaku
    total_after = sum(new_table.scores) + new_table.kyoutaku
    assert total_before == total_after

    # 三家并列 1 位，供托 10000（均分 3333/3333/3333，余数 1 分给第一位）
    # 10000 // 3 = 3333, 10000 % 3 = 1
    table = replace(
        initial_table_snapshot(starting_dealer_seat=0),
        scores=(30000, 30000, 30000, 10000),
        kyoutaku=10000,
    )
    ranking, new_table = final_settlement(table)
    # 同分者并列 1 位
    assert ranking == (1, 1, 1, 4)
    # 排序顺序：起家 0 → 下家 1 → 对家 2
    # 余数 1 分给第一个（seat 0）
    assert new_table.scores[0] == 30000 + 3333 + 1  # 第一个得余数
    assert new_table.scores[1] == 30000 + 3333
    assert new_table.scores[2] == 30000 + 3333
    # 验证点棒守恒
    total_before = sum(table.scores) + table.kyoutaku
    total_after = sum(new_table.scores) + new_table.kyoutaku
    assert total_before == total_after

    # 起家 = 2，三家并列，供托有余数
    # 分数：seat 0=30000, seat 1=25000, seat 2=30000, seat 3=30000
    # 排序顺序：seat 2 (距离0) → seat 3 (距离1) → seat 0 (距离2)
    table = replace(
        initial_table_snapshot(starting_dealer_seat=2),
        scores=(30000, 25000, 30000, 30000),  # 0, 2, 3 同分
        kyoutaku=7000,  # 7000 // 3 = 2333, 7000 % 3 = 1
    )
    ranking, new_table = final_settlement(table)
    assert ranking == (1, 4, 1, 1)
    # 排序顺序：seat 2 (距离0) → seat 3 (距离1) → seat 0 (距离2)
    # 余数 1 分给 seat 2
    assert new_table.scores[2] == 30000 + 2333 + 1  # 第一个得余数
    assert new_table.scores[3] == 30000 + 2333
    assert new_table.scores[0] == 30000 + 2333
    total_before = sum(table.scores) + table.kyoutaku
    total_after = sum(new_table.scores) + new_table.kyoutaku
    assert total_before == total_after
