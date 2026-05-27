"""PlayerReducer决策计数测试 - 验证total_decisions统计正确性。

测试用例：
1. decision records 无 latency_ms，但 total_decisions 正确计数
2. decision records 有 latency_ms，total_decisions 和 avg_latency_ms 都正确
3. player_metrics.csv 中四家 total_decisions 之和等于 decision_metrics.csv 行数
4. baseline policy 的 total_decisions 不得为 0
"""

from __future__ import annotations

import pytest

from metrics.schema import MetricRecord
from metrics.reducers import PlayerReducer


class TestPlayerReducerDecisionCount:
    """验证PlayerReducer的total_decisions统计正确性。"""

    def test_total_decisions_without_latency(self) -> None:
        """decision records 无 latency_ms，但 total_decisions 正确计数。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000, 25000, 25000, 25000)},
            ),
            # Seat 0 的 decisions（无 latency_ms）
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
        ]

        result = reducer.reduce(records)

        # 按 seat 排序
        result = sorted(result, key=lambda p: p.seat)

        # Seat 0 应该有 3 个 decisions
        assert result[0].total_decisions == 3, (
            f"Seat 0 total_decisions 应为 3，实际为 {result[0].total_decisions}"
        )

        # 没有 latency，avg_latency_ms 应为 0
        assert result[0].avg_latency_ms == 0.0

    def test_total_decisions_with_latency(self) -> None:
        """decision records 有 latency_ms，total_decisions 和 avg_latency_ms 都正确。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000, 25000, 25000, 25000)},
            ),
            # Seat 0 的 decisions（有 latency_ms）
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"latency_ms": 100.0, "parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"latency_ms": 200.0, "parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},  # 无 latency
            ),
        ]

        result = reducer.reduce(records)

        # 按 seat 排序
        result = sorted(result, key=lambda p: p.seat)

        # Seat 0 应该有 3 个 decisions
        assert result[0].total_decisions == 3, (
            f"Seat 0 total_decisions 应为 3，实际为 {result[0].total_decisions}"
        )

        # 有 latency 的记录：(100 + 200) / 2 = 150
        assert result[0].avg_latency_ms == pytest.approx(150.0)

    def test_all_seats_total_decisions_sum(self) -> None:
        """player_metrics 中四家 total_decisions 之和等于 decision 记录总数。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000, 25000, 25000, 25000)},
            ),
            # Seat 0: 2 个 decisions
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
            # Seat 1: 1 个 decision
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=1,
                values={"parse_status": "ok"},
            ),
            # Seat 2: 3 个 decisions
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=2,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=2,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=2,
                values={"parse_status": "ok"},
            ),
            # Seat 3: 0 个 decisions
        ]

        result = reducer.reduce(records)

        # 按 seat 排序
        result = sorted(result, key=lambda p: p.seat)

        # 四家 total_decisions 之和
        total = sum(p.total_decisions for p in result)

        # decision 记录总数 = 2 + 1 + 3 + 0 = 6
        assert total == 6, (
            f"四家 total_decisions 之和应为 6，实际为 {total}"
        )

    def test_baseline_policy_total_decisions_not_zero(self) -> None:
        """baseline policy 的 total_decisions 不得为 0。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000, 25000, 25000, 25000)},
            ),
            # 模拟 baseline policy（无 latency，但有 decisions）
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=1,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=2,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=3,
                values={"parse_status": "ok"},
            ),
        ]

        result = reducer.reduce(records)

        # 按 seat 排序
        result = sorted(result, key=lambda p: p.seat)

        # 每家的 total_decisions 都不应为 0
        for p in result:
            assert p.total_decisions > 0, (
                f"Seat {p.seat} total_decisions 不应为 0"
            )

    def test_mixed_latency_decisions(self) -> None:
        """混合有无 latency 的 decisions，total_decisions 正确计数。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000, 25000, 25000, 25000)},
            ),
            # Seat 0: 5 个 decisions，只有 2 个有 latency
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"latency_ms": 100.0, "parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"latency_ms": 200.0, "parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok"},
            ),
        ]

        result = reducer.reduce(records)

        # 按 seat 排序
        result = sorted(result, key=lambda p: p.seat)

        # Seat 0 应该有 5 个 decisions
        assert result[0].total_decisions == 5, (
            f"Seat 0 total_decisions 应为 5，实际为 {result[0].total_decisions}"
        )

        # 有 latency 的记录：(100 + 200) / 2 = 150
        assert result[0].avg_latency_ms == pytest.approx(150.0)