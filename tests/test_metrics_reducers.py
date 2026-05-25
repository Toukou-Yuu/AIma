"""测试 metrics reducers。

测试每个 reducer 能正确聚合 records。
"""

from __future__ import annotations

import pytest

from metrics.schema import MetricRecord
from metrics.reducers import MatchReducer, DecisionReducer, PlayerReducer


class TestMatchReducer:
    """MatchReducer 测试。"""

    def test_reduces_match_end_record(self) -> None:
        """聚合 match_end 记录。"""
        reducer = MatchReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={
                    "seed": 42,
                    "outcome": "completed",
                    "step_count": 100,
                    "duration_ms": 5000.0,
                    "final_points": (35000, 28000, 22000, 15000),
                    "point_delta": (10000, 3000, -3000, -10000),
                    "starting_points": (25000, 25000, 25000, 25000),
                },
            ),
        ]

        result = reducer.reduce(records)

        assert len(result) == 1
        m = result[0]
        assert m.match_id == "m1"
        assert m.job_id == "j1"
        assert m.seed == 42
        assert m.outcome == "completed"
        assert m.step_count == 100
        assert m.total_duration_ms == 5000.0
        assert m.final_points == (35000, 28000, 22000, 15000)
        assert m.point_delta == (10000, 3000, -3000, -10000)

    def test_counts_hand_over_events(self) -> None:
        """统计 hand_over 事件。"""
        reducer = MatchReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={},
            ),
            MetricRecord(kind="hand_over", match_id="m1", job_id="j1", values={}),
            MetricRecord(kind="hand_over", match_id="m1", job_id="j1", values={}),
            MetricRecord(kind="hand_over", match_id="m1", job_id="j1", values={}),
        ]

        result = reducer.reduce(records)

        assert result[0].hand_count == 3

    def test_aggregates_win_stats(self) -> None:
        """聚合荣和、自摸、立直统计。"""
        reducer = MatchReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={},
            ),
            # 荣和：seat 0 赢 2 次
            MetricRecord(
                kind="ron",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"winner_seat": 0},
            ),
            MetricRecord(
                kind="ron",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"winner_seat": 0},
            ),
            # 自摸：seat 1 赢 1 次
            MetricRecord(
                kind="tsumo",
                match_id="m1",
                job_id="j1",
                seat=1,
                values={"winner_seat": 1},
            ),
            # 立直：seat 2 声明 2 次，其中 1 次成功
            MetricRecord(
                kind="riichi",
                match_id="m1",
                job_id="j1",
                seat=2,
                values={"success": True},
            ),
            MetricRecord(
                kind="riichi",
                match_id="m1",
                job_id="j1",
                seat=2,
                values={"success": False},
            ),
        ]

        result = reducer.reduce(records)

        m = result[0]
        assert m.ron_count == (2, 0, 0, 0)
        assert m.tsumo_count == (0, 1, 0, 0)
        assert m.riichi_count == (0, 0, 2, 0)
        assert m.riichi_success_count == (0, 0, 1, 0)

    def test_aggregates_decision_stats(self) -> None:
        """聚合 decision 记录的 token 和延迟统计。"""
        reducer = MatchReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={
                    "parse_status": "ok",
                    "latency_ms": 100.0,
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                },
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={
                    "parse_status": "ok",
                    "latency_ms": 200.0,
                    "prompt_tokens": 2000,
                    "completion_tokens": 200,
                },
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={
                    "parse_status": "fallback",
                    "latency_ms": 150.0,
                    "prompt_tokens": 1500,
                },
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={
                    "parse_status": "error",
                    "latency_ms": 50.0,
                    "prompt_tokens": 500,
                },
            ),
        ]

        result = reducer.reduce(records)

        m = result[0]
        assert m.decision_count == 4
        assert m.parse_success_count == 2
        assert m.parse_fallback_count == 1
        assert m.parse_error_count == 1
        assert m.total_prompt_tokens == 5000
        assert m.total_completion_tokens == 500  # 100 + 200 + heuristic 150 + 50
        assert m.avg_latency_ms == 125.0  # (100+200+150+50)/4
        assert m.memory_injected_tokens_total == 0

    def test_handles_multiple_matches(self) -> None:
        """处理多个 match。"""
        reducer = MatchReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"seed": 1},
            ),
            MetricRecord(
                kind="hand_over",
                match_id="m1",
                job_id="j1",
                values={},
            ),
            MetricRecord(
                kind="match_end",
                match_id="m2",
                job_id="j2",
                values={"seed": 2},
            ),
            MetricRecord(
                kind="hand_over",
                match_id="m2",
                job_id="j2",
                values={},
            ),
            MetricRecord(
                kind="hand_over",
                match_id="m2",
                job_id="j2",
                values={},
            ),
        ]

        result = reducer.reduce(records)

        assert len(result) == 2
        match_ids = {m.match_id for m in result}
        assert match_ids == {"m1", "m2"}

    def test_handles_missing_token_data(self) -> None:
        """处理缺少 token 数据的情况。"""
        reducer = MatchReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={
                    "parse_status": "ok",
                    "latency_ms": None,
                },
            ),
        ]

        result = reducer.reduce(records)

        m = result[0]
        assert m.total_prompt_tokens == 0
        assert m.total_completion_tokens == 0
        assert m.avg_latency_ms == 0.0

    def test_calculates_p99_latency(self) -> None:
        """计算 p99 延迟。"""
        reducer = MatchReducer()
        # 创建 100 个 decision，延迟从 10 到 100
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={},
            ),
        ]
        for i in range(100):
            records.append(
                MetricRecord(
                    kind="decision",
                    match_id="m1",
                    job_id="j1",
                    values={
                        "latency_ms": float(i + 1),
                        "parse_status": "ok",
                    },
                )
            )

        result = reducer.reduce(records)

        m = result[0]
        # p99 = 第 99 个值（索引 99）= 100
        assert m.p99_latency_ms == 100.0

    def test_peaks_prompt_tokens(self) -> None:
        """追踪峰值 prompt tokens。"""
        reducer = MatchReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={"prompt_tokens": 1000},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={"prompt_tokens": 5000},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                values={"prompt_tokens": 2000},
            ),
        ]

        result = reducer.reduce(records)

        assert result[0].peak_prompt_tokens == 5000


class TestDecisionReducer:
    """DecisionReducer 测试。"""

    def test_extracts_decision_records(self) -> None:
        """提取 decision 记录。"""
        reducer = DecisionReducer()
        records = [
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                hand_index=1,
                values={
                    "step_index": 30,
                    "parse_status": "ok",
                    "fallback_used": False,
                    "latency_ms": 150.5,
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                    "memory_injected_tokens": 200,
                    "action_kind": "discard",
                },
            ),
        ]

        result = reducer.reduce(records)

        assert len(result) == 1
        d = result[0]
        assert d.match_id == "m1"
        assert d.job_id == "j1"
        assert d.seat == 0
        assert d.hand_index == 1
        assert d.step_index == 30
        assert d.parse_status == "ok"
        assert d.fallback_used is False
        assert d.latency_ms == 150.5
        assert d.prompt_tokens == 1000
        assert d.completion_tokens == 100
        assert d.memory_injected_tokens == 200
        assert d.action_kind == "discard"

    def test_filters_non_decision_records(self) -> None:
        """过滤非 decision 记录。"""
        reducer = DecisionReducer()
        records = [
            MetricRecord(kind="match_end", match_id="m1", job_id="j1", values={}),
            MetricRecord(kind="hand_over", match_id="m1", job_id="j1", values={}),
            MetricRecord(kind="ron", match_id="m1", job_id="j1", values={}),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok", "action_kind": "unknown"},
            ),
        ]

        result = reducer.reduce(records)

        assert len(result) == 1

    def test_handles_missing_values(self) -> None:
        """处理缺少的值。"""
        reducer = DecisionReducer()
        records = [
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=1,
                values={},
            ),
        ]

        result = reducer.reduce(records)

        d = result[0]
        assert d.parse_status == "ok"  # 默认值
        assert d.fallback_used is False  # 默认值
        assert d.latency_ms is None
        assert d.prompt_tokens is None
        assert d.completion_tokens is None
        assert d.memory_injected_tokens is None
        assert d.action_kind == "unknown"  # 默认值

    def test_processes_multiple_decisions(self) -> None:
        """处理多个 decision。"""
        reducer = DecisionReducer()
        records = [
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={"parse_status": "ok", "action_kind": "discard"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=1,
                values={"parse_status": "fallback", "action_kind": "call"},
            ),
            MetricRecord(
                kind="decision",
                match_id="m2",
                job_id="j2",
                seat=2,
                values={"parse_status": "error", "action_kind": "riichi"},
            ),
        ]

        result = reducer.reduce(records)

        assert len(result) == 3
        assert result[0].seat == 0
        assert result[1].seat == 1
        assert result[2].match_id == "m2"


class TestPlayerReducer:
    """PlayerReducer 测试。"""

    def test_aggregates_points_per_seat(self) -> None:
        """聚合每个 seat 的点数。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={
                    "final_points": (35000, 28000, 22000, 15000),
                    "point_delta": (10000, 3000, -3000, -10000),
                },
            ),
            MetricRecord(
                kind="match_end",
                match_id="m2",
                job_id="j2",
                values={
                    "final_points": (30000, 25000, 25000, 20000),
                    "point_delta": (5000, 0, 0, -5000),
                },
            ),
        ]

        result = reducer.reduce(records)

        assert len(result) == 4
        # Seat 0: avg (35000+30000)/2 = 32500, total delta = 15000
        assert result[0].seat == 0
        assert result[0].match_count == 2
        assert result[0].avg_final_points == 32500.0
        assert result[0].total_point_delta == 15000
        # Seat 1: avg (28000+25000)/2 = 26500, total delta = 3000
        assert result[1].seat == 1
        assert result[1].avg_final_points == 26500.0
        assert result[1].total_point_delta == 3000
        # Seat 2: avg (22000+25000)/2 = 23500
        assert result[2].avg_final_points == 23500.0
        # Seat 3: avg (15000+20000)/2 = 17500
        assert result[3].avg_final_points == 17500.0

    def test_aggregates_wins_per_seat(self) -> None:
        """聚合每个 seat 的荣和、自摸、立直。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000, 25000, 25000, 25000)},
            ),
            # Seat 0 荣和 2 次
            MetricRecord(kind="ron", match_id="m1", job_id="j1", seat=0, values={"winner_seat": 0}),
            MetricRecord(kind="ron", match_id="m1", job_id="j1", seat=0, values={"winner_seat": 0}),
            # Seat 1 自摸 1 次
            MetricRecord(kind="tsumo", match_id="m1", job_id="j1", seat=1, values={"winner_seat": 1}),
            # Seat 2 立直 3 次，2 次成功
            MetricRecord(kind="riichi", match_id="m1", job_id="j1", seat=2, values={"success": True}),
            MetricRecord(kind="riichi", match_id="m1", job_id="j1", seat=2, values={"success": True}),
            MetricRecord(kind="riichi", match_id="m1", job_id="j1", seat=2, values={"success": False}),
        ]

        result = reducer.reduce(records)

        # 按 seat 排序
        result = sorted(result, key=lambda p: p.seat)

        assert result[0].total_ron_count == 2
        assert result[0].total_tsumo_count == 0
        assert result[1].total_ron_count == 0
        assert result[1].total_tsumo_count == 1
        assert result[2].total_riichi_count == 3
        assert result[2].riichi_success_rate == pytest.approx(2 / 3)

    def test_aggregates_decision_stats_per_seat(self) -> None:
        """聚合每个 seat 的 decision 统计。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000, 25000, 25000, 25000)},
            ),
            # Seat 0 的 decisions
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={
                    "latency_ms": 100.0,
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                    "parse_status": "ok",
                },
            ),
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=0,
                values={
                    "latency_ms": 200.0,
                    "prompt_tokens": 2000,
                    "completion_tokens": 200,
                    "parse_status": "ok",
                },
            ),
            # Seat 1 的 decision
            MetricRecord(
                kind="decision",
                match_id="m1",
                job_id="j1",
                seat=1,
                values={
                    "latency_ms": 150.0,
                    "prompt_tokens": 1500,
                    "completion_tokens": 150,
                    "parse_status": "fallback",
                },
            ),
        ]

        result = reducer.reduce(records)
        result = sorted(result, key=lambda p: p.seat)

        # Seat 0
        assert result[0].total_decisions == 2
        assert result[0].avg_latency_ms == 150.0
        assert result[0].avg_prompt_tokens == 1500.0
        assert result[0].total_tokens == 3300  # 1000+100 + 2000+200
        assert result[0].parse_success_rate == 1.0

        # Seat 1
        assert result[1].total_decisions == 1
        assert result[1].avg_latency_ms == 150.0
        assert result[1].parse_success_rate == 0.0

    def test_handles_empty_records(self) -> None:
        """处理空记录列表。"""
        reducer = PlayerReducer()
        records: list[MetricRecord] = []

        result = reducer.reduce(records)

        assert len(result) == 0

    def test_handles_single_seat(self) -> None:
        """处理只有一个 seat 的情况。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={
                    "final_points": (35000, 25000, 25000, 25000),
                    "point_delta": (10000, 0, 0, 0),
                },
            ),
            MetricRecord(kind="ron", match_id="m1", job_id="j1", seat=0, values={"winner_seat": 0}),
        ]

        result = reducer.reduce(records)

        # 仍然返回 4 个 seat（因为 match_end 会填充所有 seat）
        assert len(result) == 4

    def test_calculates_p99_latency(self) -> None:
        """计算 p99 延迟。"""
        reducer = PlayerReducer()
        records = [
            MetricRecord(
                kind="match_end",
                match_id="m1",
                job_id="j1",
                values={"final_points": (25000,) * 4},
            ),
        ]
        # 添加 50 个 decision，延迟从 50 到 100
        for i in range(50):
            records.append(
                MetricRecord(
                    kind="decision",
                    match_id="m1",
                    job_id="j1",
                    seat=0,
                    values={"latency_ms": float(50 + i), "parse_status": "ok"},
                )
            )

        result = reducer.reduce(records)
        result = sorted(result, key=lambda p: p.seat)

        # p99 = 第 49 个值（50 + 49 = 99）
        assert result[0].p99_latency_ms == 99.0


class TestReducerProtocol:
    """测试 reducer 协议一致性。"""

    def test_all_reducers_have_name(self) -> None:
        """所有 reducer 都有 name 属性。"""
        reducers = [
            MatchReducer(),
            DecisionReducer(),
            PlayerReducer(),
        ]

        for r in reducers:
            assert hasattr(r, "name")
            assert isinstance(r.name, str)
            assert len(r.name) > 0

    def test_match_reducer_returns_list(self) -> None:
        """MatchReducer 返回列表。"""
        reducer = MatchReducer()
        records: list[MetricRecord] = []

        result = reducer.reduce(records)

        assert isinstance(result, list)

    def test_decision_reducer_returns_list(self) -> None:
        """DecisionReducer 返回列表。"""
        reducer = DecisionReducer()
        records: list[MetricRecord] = []

        result = reducer.reduce(records)

        assert isinstance(result, list)

    def test_player_reducer_returns_list(self) -> None:
        """PlayerReducer 返回列表。"""
        reducer = PlayerReducer()
        records: list[MetricRecord] = []

        result = reducer.reduce(records)

        assert isinstance(result, list)