"""测试 metrics pipeline。

测试 pipeline 能正确处理完整流程。
"""

from __future__ import annotations

import pytest

from metrics.loader import DecisionRecord, EventRecord, RunData
from metrics.pipeline import MetricsPipeline, create_default_pipeline
from metrics.extractors import (
    CallExtractor,
    DecisionExtractor,
    FlowExtractor,
    HandOverExtractor,
    MatchEndExtractor,
    RiichiExtractor,
    RonExtractor,
    TsumoExtractor,
)
from metrics.reducers import DecisionReducer, MatchReducer, PlayerReducer
from metrics.schema import MetricRecord


class TestMetricsPipeline:
    """MetricsPipeline 测试。"""

    def test_runs_extractors_and_reducers(self) -> None:
        """运行 extractors 和 reducers。"""
        pipeline = MetricsPipeline(
            extractors=[MatchEndExtractor(), HandOverExtractor()],
            reducers=[MatchReducer()],
        )

        # 创建测试数据
        events = [
            EventRecord(
                match_id="m1",
                step_index=100,
                event={
                    "event_type": "match_end",
                    "ranking": [1, 2, 3, 4],
                    "final_scores": [35000, 28000, 22000, 15000],
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=10,
                event={"event_type": "hand_over", "winners": []},
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={"event_type": "hand_over", "winners": []},
            ),
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=events,
            summary=None,
        )

        result = pipeline.run([data])

        # 应包含 match reducer 的结果
        assert "match" in result
        match_metrics = result["match"]
        assert len(match_metrics) == 1
        assert match_metrics[0].match_id == "m1"
        assert match_metrics[0].hand_count == 2

    def test_runs_multiple_reducers(self) -> None:
        """运行多个 reducers。"""
        pipeline = MetricsPipeline(
            extractors=[DecisionExtractor()],
            reducers=[DecisionReducer(), PlayerReducer()],
        )

        decisions = [
            DecisionRecord(
                match_id="m1",
                step_index=10,
                seat=0,
                action={"kind": "discard"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=100.0,
                diagnostics={"prompt_tokens": 1000},
            ),
            DecisionRecord(
                match_id="m1",
                step_index=20,
                seat=1,
                action={"kind": "call"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=150.0,
                diagnostics={"prompt_tokens": 2000},
            ),
        ]
        events = [
            EventRecord(
                match_id="m1",
                step_index=100,
                event={
                    "event_type": "match_end",
                    "final_points": (35000, 28000, 22000, 15000),
                    "point_delta": (10000, 3000, -3000, -10000),
                },
            ),
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=decisions,
            events=events,
            summary=None,
        )

        result = pipeline.run([data])

        assert "decision" in result
        assert "player" in result
        assert len(result["decision"]) == 2
        assert len(result["player"]) == 2  # 只有 seat 0 和 1 有 decisions

    def test_processes_multiple_run_data(self) -> None:
        """处理多个 RunData。"""
        pipeline = MetricsPipeline(
            extractors=[MatchEndExtractor(), HandOverExtractor()],
            reducers=[MatchReducer()],
        )

        # 创建两个 match
        data1 = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=[
                EventRecord(
                    match_id="m1",
                    step_index=100,
                    event={
                        "event_type": "match_end",
                        "final_points": (35000, 25000, 25000, 15000),
                    },
                ),
                EventRecord(
                    match_id="m1",
                    step_index=10,
                    event={"event_type": "hand_over"},
                ),
            ],
            summary=None,
        )
        data2 = RunData(
            match_id="m2",
            job_id="j2",
            seed=43,
            decisions=[],
            events=[
                EventRecord(
                    match_id="m2",
                    step_index=100,
                    event={
                        "event_type": "match_end",
                        "final_points": (28000, 28000, 24000, 20000),
                    },
                ),
                EventRecord(
                    match_id="m2",
                    step_index=10,
                    event={"event_type": "hand_over"},
                ),
                EventRecord(
                    match_id="m2",
                    step_index=20,
                    event={"event_type": "hand_over"},
                ),
            ],
            summary=None,
        )

        result = pipeline.run([data1, data2])

        match_metrics = result["match"]
        assert len(match_metrics) == 2
        match_ids = {m.match_id for m in match_metrics}
        assert match_ids == {"m1", "m2"}

    def test_empty_run_data(self) -> None:
        """处理空 RunData 列表。"""
        pipeline = MetricsPipeline(
            extractors=[MatchEndExtractor()],
            reducers=[MatchReducer()],
        )

        result = pipeline.run([])

        assert "match" in result
        assert len(result["match"]) == 0

    def test_uses_default_pipeline(self) -> None:
        """使用默认 pipeline。"""
        pipeline = create_default_pipeline()

        # 验证 extractors
        assert len(pipeline.extractors) == 8
        extractor_names = {e.name for e in pipeline.extractors}
        assert extractor_names == {
            "match_end",
            "hand_over",
            "decision",
            "ron",
            "tsumo",
            "riichi",
            "call",
            "flow",
        }

        # 验证 reducers
        assert len(pipeline.reducers) == 3
        reducer_names = {r.name for r in pipeline.reducers}
        assert reducer_names == {"match", "decision", "player"}

    def test_default_pipeline_full_flow(self) -> None:
        """默认 pipeline 完整流程。"""
        pipeline = create_default_pipeline()

        # 创建完整测试数据
        events = [
            EventRecord(
                match_id="m1",
                step_index=100,
                event={
                    "event_type": "match_end",
                    "ranking": [1, 2, 3, 4],
                    "final_scores": [35000, 28000, 22000, 15000],
                    "final_points": (35000, 28000, 22000, 15000),
                    "point_delta": (10000, 3000, -3000, -10000),
                    "starting_points": (25000, 25000, 25000, 25000),
                    "seed": 42,
                    "outcome": "completed",
                    "step_count": 100,
                    "duration_ms": 5000.0,
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=10,
                event={"event_type": "hand_over", "winners": [0]},
            ),
            EventRecord(
                match_id="m1",
                step_index=15,
                event={
                    "event_type": "ron",
                    "seat": 0,
                    "win_tile": "1m",
                    "discard_seat": 2,
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={"event_type": "hand_over", "winners": []},
            ),
            EventRecord(
                match_id="m1",
                step_index=25,
                event={
                    "event_type": "tsumo",
                    "seat": 1,
                    "win_tile": "5z",
                    "is_rinshan": False,
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=30,
                event={
                    "event_type": "discard_tile",
                    "seat": 2,
                    "tile": "2p",
                    "declare_riichi": True,
                    "is_tsumogiri": False,
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=35,
                event={
                    "event_type": "call",
                    "seat": 3,
                    "call_kind": "pon",
                    "meld": {"kind": "pon"},
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=40,
                event={
                    "event_type": "flow",
                    "flow_kind": "exhaustive_draw",
                    "tenpai_seats": [0, 2],
                },
            ),
        ]
        decisions = [
            DecisionRecord(
                match_id="m1",
                step_index=10,
                seat=0,
                action={"kind": "discard", "tile": "1m"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=100.0,
                diagnostics={
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                    "memory_injected_tokens": 200,
                },
            ),
            DecisionRecord(
                match_id="m1",
                step_index=20,
                seat=1,
                action={"kind": "draw"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=150.0,
                diagnostics={
                    "prompt_tokens": 2000,
                    "completion_tokens": 200,
                    "memory_injected_tokens": 300,
                },
            ),
            DecisionRecord(
                match_id="m1",
                step_index=30,
                seat=2,
                action={"kind": "riichi"},
                parse_status="fallback",
                fallback_used=True,
                latency_ms=200.0,
                diagnostics={},
            ),
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=decisions,
            events=events,
            summary=None,
        )

        result = pipeline.run([data])

        # 验证结果
        assert "match" in result
        assert "decision" in result
        assert "player" in result

        # match metrics
        match_metrics = result["match"]
        assert len(match_metrics) == 1
        m = match_metrics[0]
        assert m.match_id == "m1"
        assert m.hand_count == 2
        assert m.ron_count == (1, 0, 0, 0)
        assert m.tsumo_count == (0, 1, 0, 0)
        assert m.riichi_count == (0, 0, 1, 0)
        assert m.decision_count == 3

        # decision metrics
        decision_metrics = result["decision"]
        assert len(decision_metrics) == 3
        assert decision_metrics[0].parse_status == "ok"
        assert decision_metrics[2].parse_status == "fallback"

        # player metrics
        player_metrics = result["player"]
        assert len(player_metrics) == 4


class TestPipelineIntegration:
    """Pipeline 集成测试。"""

    def test_combines_records_from_all_extractors(self) -> None:
        """合并所有 extractors 的记录。"""
        pipeline = create_default_pipeline()

        # 只创建一个简单 match
        events = [
            EventRecord(
                match_id="m1",
                step_index=100,
                event={
                    "event_type": "match_end",
                    "final_points": (25000, 25000, 25000, 25000),
                },
            ),
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=events,
            summary=None,
        )

        result = pipeline.run([data])

        # 即使只有 match_end，也应该产生结果
        assert len(result["match"]) == 1
        assert len(result["player"]) == 4

    def test_extractor_produces_correct_record_count(self) -> None:
        """验证 extractor 产生正确的记录数量。"""
        pipeline = MetricsPipeline(
            extractors=[RonExtractor(), TsumoExtractor()],
            reducers=[MatchReducer()],
        )

        events = [
            EventRecord(
                match_id="m1",
                step_index=100,
                event={
                    "event_type": "match_end",
                    "final_points": (25000, 25000, 25000, 25000),
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=10,
                event={"event_type": "ron", "seat": 0},
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={"event_type": "ron", "seat": 1},
            ),
            EventRecord(
                match_id="m1",
                step_index=30,
                event={"event_type": "tsumo", "seat": 2},
            ),
            EventRecord(
                match_id="m1",
                step_index=40,
                event={"event_type": "tsumo", "seat": 3},
            ),
            EventRecord(
                match_id="m1",
                step_index=50,
                event={"event_type": "tsumo", "seat": 0},
            ),
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=events,
            summary=None,
        )

        result = pipeline.run([data])

        m = result["match"][0]
        assert m.ron_count == (1, 1, 0, 0)
        assert m.tsumo_count == (1, 0, 1, 1)

    def test_records_preserve_match_and_job_ids(self) -> None:
        """记录保留 match_id 和 job_id。"""
        pipeline = MetricsPipeline(
            extractors=[DecisionExtractor()],
            reducers=[DecisionReducer()],
        )

        decisions = [
            DecisionRecord(
                match_id="match_abc",
                step_index=10,
                seat=0,
                action={"kind": "discard"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=100.0,
                diagnostics={},
            ),
        ]
        data = RunData(
            match_id="match_abc",
            job_id="job_xyz",
            seed=42,
            decisions=decisions,
            events=[],
            summary=None,
        )

        result = pipeline.run([data])

        d = result["decision"][0]
        assert d.match_id == "match_abc"
        assert d.job_id == "job_xyz"

    def test_handles_large_data_volume(self) -> None:
        """处理大量数据。"""
        pipeline = create_default_pipeline()

        # 创建 10 个 match
        run_data_list: list[RunData] = []
        for i in range(10):
            events = [
                EventRecord(
                    match_id=f"m{i}",
                    step_index=100,
                    event={
                        "event_type": "match_end",
                        "final_points": (25000, 25000, 25000, 25000),
                    },
                ),
            ]
            decisions = [
                DecisionRecord(
                    match_id=f"m{i}",
                    step_index=j,
                    seat=j % 4,
                    action={"kind": "discard"},
                    parse_status="ok",
                    fallback_used=False,
                    latency_ms=100.0 + j,
                    diagnostics={"prompt_tokens": 1000 + j},
                )
                for j in range(10)
            ]
            run_data_list.append(
                RunData(
                    match_id=f"m{i}",
                    job_id=f"j{i}",
                    seed=42 + i,
                    decisions=decisions,
                    events=events,
                    summary=None,
                )
            )

        result = pipeline.run(run_data_list)

        assert len(result["match"]) == 10
        assert len(result["decision"]) == 100  # 10 match * 10 decisions
        assert len(result["player"]) == 4

        # 验证 player 跨 match 聚合
        for p in result["player"]:
            assert p.match_count == 10


class TestPipelineEmptyCases:
    """Pipeline 空数据测试。"""

    def test_empty_decisions(self) -> None:
        """空 decisions。"""
        pipeline = MetricsPipeline(
            extractors=[DecisionExtractor()],
            reducers=[DecisionReducer()],
        )

        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=[],
            summary=None,
        )

        result = pipeline.run([data])

        assert len(result["decision"]) == 0

    def test_empty_events(self) -> None:
        """空 events。"""
        pipeline = MetricsPipeline(
            extractors=[MatchEndExtractor()],
            reducers=[MatchReducer()],
        )

        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=[],
            summary=None,
        )

        result = pipeline.run([data])

        assert len(result["match"]) == 0

    def test_no_matching_events(self) -> None:
        """没有匹配的 events。"""
        pipeline = MetricsPipeline(
            extractors=[RonExtractor()],
            reducers=[MatchReducer()],
        )

        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={"event_type": "discard_tile"},
            ),
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=events,
            summary=None,
        )

        result = pipeline.run([data])

        # 没有 ron 事件，match reducer 不会产生结果
        assert len(result["match"]) == 0


class TestPipelineConfiguration:
    """Pipeline 配置测试。"""

    def test_custom_extractor_list(self) -> None:
        """自定义 extractor 列表。"""
        pipeline = MetricsPipeline(
            extractors=[MatchEndExtractor()],
            reducers=[MatchReducer()],
        )

        assert len(pipeline.extractors) == 1
        assert pipeline.extractors[0].name == "match_end"

    def test_custom_reducer_list(self) -> None:
        """自定义 reducer 列表。"""
        pipeline = MetricsPipeline(
            extractors=[DecisionExtractor()],
            reducers=[DecisionReducer()],
        )

        assert len(pipeline.reducers) == 1
        assert pipeline.reducers[0].name == "decision"

    def test_can_add_custom_extractor(self) -> None:
        """可以添加自定义 extractor。"""
        # 创建一个简单的自定义 extractor
        class CustomExtractor:
            name = "custom"

            def extract(self, data: RunData):
                yield MetricRecord(
                    kind="match_end",  # 使用已存在的 kind
                    match_id=data.match_id,
                    job_id=data.job_id,
                    values={"custom_field": 42},
                )

        pipeline = MetricsPipeline(
            extractors=[MatchEndExtractor(), CustomExtractor()],
            reducers=[MatchReducer()],
        )

        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=[],
            summary=None,
        )

        result = pipeline.run([data])

        # 应该有两个 match_end 记录被处理
        # MatchReducer 会合并同一个 match_id 的记录
        assert len(result["match"]) == 1