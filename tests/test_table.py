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


def test_table_snapshot_negative_score_raises() -> None:
    base = initial_table_snapshot()
    with pytest.raises(ValueError, match="scores\\[0\\]"):
        replace(base, scores=(-1, 0, 0, 0))


def test_nonzero_honba_kyoutaku_valid() -> None:
    s = initial_table_snapshot(honba=2, kyoutaku=3000)
    assert s.honba == 2
    assert s.kyoutaku == 3000
    assert isinstance(s, TableSnapshot)


def test_tonpuu_preset() -> None:
    s = initial_table_snapshot(match_preset=MatchPreset.TONPUSEN)
    assert s.match_preset == MatchPreset.TONPUSEN
