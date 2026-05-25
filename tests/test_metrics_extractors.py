"""测试 metrics extractors。

测试每个 extractor 能正确从 RunData 提取 MetricRecord。
"""

from __future__ import annotations

import pytest

from metrics.loader import DecisionRecord, EventRecord, JobSummary, RunData
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


class TestMatchEndExtractor:
    """MatchEndExtractor 测试。"""

    def test_extracts_match_end_event(self) -> None:
        """提取 match_end 事件。"""
        extractor = MatchEndExtractor()
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
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=events,
            summary=None,
        )

        records = list(extractor.extract(data))

        assert len(records) == 1
        record = records[0]
        assert record.kind == "match_end"
        assert record.match_id == "m1"
        assert record.job_id == "j1"
        assert record.seat is None
        assert record.hand_index is None
        assert record.values["ranking"] == (1, 2, 3, 4)
        assert record.values["final_scores"] == (35000, 28000, 22000, 15000)

    def test_handles_list_ranking(self) -> None:
        """正确处理 list 类型的 ranking。"""
        extractor = MatchEndExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=100,
                event={
                    "event_type": "match_end",
                    "ranking": [4, 3, 2, 1],
                    "final_scores": [15000, 22000, 28000, 35000],
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

        records = list(extractor.extract(data))

        assert records[0].values["ranking"] == (4, 3, 2, 1)
        assert records[0].values["final_scores"] == (15000, 22000, 28000, 35000)

    def test_ignores_non_match_end_events(self) -> None:
        """忽略非 match_end 事件。"""
        extractor = MatchEndExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={"event_type": "discard_tile"},
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={"event_type": "call"},
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

        records = list(extractor.extract(data))

        assert len(records) == 0

    def test_default_values_when_missing(self) -> None:
        """缺少字段时使用默认值。"""
        extractor = MatchEndExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=100,
                event={"event_type": "match_end"},
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

        records = list(extractor.extract(data))

        assert len(records) == 1
        assert records[0].values["ranking"] == (1, 1, 1, 1)
        assert records[0].values["final_scores"] == (0, 0, 0, 0)


class TestHandOverExtractor:
    """HandOverExtractor 测试。"""

    def test_extracts_hand_over_events(self) -> None:
        """提取 hand_over 事件。"""
        extractor = HandOverExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "hand_over",
                    "winners": [0],
                    "payments": [1500, -500, -500, -500],
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={
                    "event_type": "hand_over",
                    "winners": [2],
                    "payments": [-500, -500, 1500, -500],
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

        records = list(extractor.extract(data))

        assert len(records) == 2
        assert records[0].kind == "hand_over"
        assert records[0].hand_index == 0
        assert records[0].values["winners"] == (0,)
        assert records[0].values["payments"] == (1500, -500, -500, -500)
        assert records[1].hand_index == 1
        assert records[1].values["winners"] == (2,)

    def test_handles_list_payments(self) -> None:
        """正确处理 list 类型的 payments。"""
        extractor = HandOverExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "hand_over",
                    "winners": [],
                    "payments": [0, 0, 0, 0],
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

        records = list(extractor.extract(data))

        assert records[0].values["payments"] == (0, 0, 0, 0)

    def test_includes_step_index(self) -> None:
        """包含 step_index 字段。"""
        extractor = HandOverExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=25,
                event={
                    "event_type": "hand_over",
                    "winners": [],
                    "payments": [0, 0, 0, 0],
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

        records = list(extractor.extract(data))

        assert records[0].values["step_index"] == 25


class TestDecisionExtractor:
    """DecisionExtractor 测试。"""

    def test_extracts_decision_records(self) -> None:
        """提取 decision 记录。"""
        extractor = DecisionExtractor()
        decisions = [
            DecisionRecord(
                match_id="m1",
                step_index=10,
                seat=0,
                action={"kind": "discard", "tile": "1m"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=150.5,
                diagnostics={
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                    "memory_injected_tokens": 200,
                },
            ),
            DecisionRecord(
                match_id="m1",
                step_index=30,
                seat=1,
                action={"kind": "call", "call_kind": "chi"},
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
            events=[],
            summary=None,
        )

        records = list(extractor.extract(data))

        assert len(records) == 2

        # 第一个 decision
        r1 = records[0]
        assert r1.kind == "decision"
        assert r1.match_id == "m1"
        assert r1.job_id == "j1"
        assert r1.seat == 0
        assert r1.values["step_index"] == 10
        assert r1.values["parse_status"] == "ok"
        assert r1.values["fallback_used"] is False
        assert r1.values["latency_ms"] == 150.5
        assert r1.values["prompt_tokens"] == 1000
        assert r1.values["completion_tokens"] == 100
        assert r1.values["memory_injected_tokens"] == 200
        assert r1.values["action_kind"] == "discard"

        # 第二个 decision
        r2 = records[1]
        assert r2.seat == 1
        assert r2.values["parse_status"] == "fallback"
        assert r2.values["fallback_used"] is True
        assert r2.values["action_kind"] == "call"

    def test_handles_missing_diagnostics(self) -> None:
        """处理缺少 diagnostics 的情况。"""
        extractor = DecisionExtractor()
        decisions = [
            DecisionRecord(
                match_id="m1",
                step_index=10,
                seat=0,
                action={"kind": "unknown"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=None,
                diagnostics={},
            ),
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=decisions,
            events=[],
            summary=None,
        )

        records = list(extractor.extract(data))

        assert len(records) == 1
        assert records[0].values["prompt_tokens"] is None
        assert records[0].values["completion_tokens"] is None
        assert records[0].values["memory_injected_tokens"] is None
        assert records[0].values["latency_ms"] is None

    def test_estimates_hand_index(self) -> None:
        """根据 step_index 估算 hand_index。"""
        extractor = DecisionExtractor()
        decisions = [
            DecisionRecord(
                match_id="m1",
                step_index=i,
                seat=0,
                action={"kind": "discard"},
                parse_status="ok",
                fallback_used=False,
                latency_ms=None,
                diagnostics={},
            )
            for i in [0, 10, 20, 30, 60, 80]
        ]
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=decisions,
            events=[],
            summary=None,
        )

        records = list(extractor.extract(data))

        # hand_index = step_index // 25
        assert records[0].hand_index == 0  # 0 // 25
        assert records[1].hand_index == 0  # 10 // 25
        assert records[2].hand_index == 0  # 20 // 25
        assert records[3].hand_index == 1  # 30 // 25
        assert records[4].hand_index == 2  # 60 // 25
        assert records[5].hand_index == 3  # 80 // 25


class TestRonExtractor:
    """RonExtractor 测试。"""

    def test_extracts_ron_events(self) -> None:
        """提取 ron 事件。"""
        extractor = RonExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "ron",
                    "seat": 0,
                    "win_tile": "1m",
                    "discard_seat": 2,
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

        records = list(extractor.extract(data))

        assert len(records) == 1
        r = records[0]
        assert r.kind == "ron"
        assert r.seat == 0
        assert r.values["win_tile"] == "1m"
        assert r.values["discard_seat"] == 2

    def test_tracks_hand_index_via_hand_over(self) -> None:
        """通过 hand_over 事件追踪 hand_index。"""
        extractor = RonExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=5,
                event={"event_type": "hand_over", "winners": []},
            ),
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "ron",
                    "seat": 1,
                    "win_tile": "2p",
                    "discard_seat": 3,
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=15,
                event={"event_type": "hand_over", "winners": []},
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={
                    "event_type": "ron",
                    "seat": 2,
                    "win_tile": "3s",
                    "discard_seat": 0,
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

        records = list(extractor.extract(data))

        assert len(records) == 2
        assert records[0].hand_index == 1  # 在第一个 hand_over 之后
        assert records[1].hand_index == 2  # 在第二个 hand_over 之后

    def test_ignores_other_events(self) -> None:
        """忽略非 ron 事件。"""
        extractor = RonExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={"event_type": "tsumo", "seat": 0},
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={"event_type": "discard_tile", "seat": 1},
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

        records = list(extractor.extract(data))

        assert len(records) == 0


class TestTsumoExtractor:
    """TsumoExtractor 测试。"""

    def test_extracts_tsumo_events(self) -> None:
        """提取 tsumo 事件。"""
        extractor = TsumoExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "tsumo",
                    "seat": 1,
                    "win_tile": "5z",
                    "is_rinshan": False,
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

        records = list(extractor.extract(data))

        assert len(records) == 1
        r = records[0]
        assert r.kind == "tsumo"
        assert r.seat == 1
        assert r.values["win_tile"] == "5z"
        assert r.values["is_rinshan"] is False

    def test_detects_rinshan_tsumo(self) -> None:
        """检测岭上开花。"""
        extractor = TsumoExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "tsumo",
                    "seat": 0,
                    "win_tile": "1m",
                    "is_rinshan": True,
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

        records = list(extractor.extract(data))

        assert records[0].values["is_rinshan"] is True


class TestRiichiExtractor:
    """RiichiExtractor 测试。"""

    def test_extracts_riichi_declarations(self) -> None:
        """提取立直声明。"""
        extractor = RiichiExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "discard_tile",
                    "seat": 0,
                    "tile": "1m",
                    "declare_riichi": True,
                    "is_tsumogiri": False,
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

        records = list(extractor.extract(data))

        assert len(records) == 1
        r = records[0]
        assert r.kind == "riichi"
        assert r.seat == 0
        assert r.values["tile"] == "1m"
        assert r.values["is_tsumogiri"] is False

    def test_ignores_normal_discards(self) -> None:
        """忽略普通打牌（非立直）。"""
        extractor = RiichiExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "discard_tile",
                    "seat": 0,
                    "tile": "1m",
                    "declare_riichi": False,
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={
                    "event_type": "discard_tile",
                    "seat": 1,
                    "tile": "2p",
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

        records = list(extractor.extract(data))

        assert len(records) == 0

    def test_tracks_hand_index(self) -> None:
        """追踪 hand_index。"""
        extractor = RiichiExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=5,
                event={
                    "event_type": "discard_tile",
                    "seat": 0,
                    "tile": "1m",
                    "declare_riichi": True,
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=10,
                event={"event_type": "hand_over", "winners": []},
            ),
            EventRecord(
                match_id="m1",
                step_index=15,
                event={
                    "event_type": "discard_tile",
                    "seat": 2,
                    "tile": "3s",
                    "declare_riichi": True,
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

        records = list(extractor.extract(data))

        assert len(records) == 2
        assert records[0].hand_index == 0
        assert records[1].hand_index == 1


class TestCallExtractor:
    """CallExtractor 测试。"""

    def test_extracts_call_events(self) -> None:
        """提取 call 事件。"""
        extractor = CallExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "call",
                    "seat": 1,
                    "call_kind": "chi",
                    "meld": {"kind": "chi", "tiles": ["1m", "2m", "3m"]},
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

        records = list(extractor.extract(data))

        assert len(records) == 1
        r = records[0]
        assert r.kind == "call"
        assert r.seat == 1
        assert r.values["call_kind"] == "chi"
        assert r.values["meld_type"] == "chi"
        assert r.values["is_kan"] is False

    def test_detects_kan_calls(self) -> None:
        """检测杠子。"""
        extractor = CallExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "call",
                    "seat": 0,
                    "call_kind": "ankan",
                    "meld": {"kind": "ankan"},
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=20,
                event={
                    "event_type": "call",
                    "seat": 1,
                    "call_kind": "daiminkan",
                    "meld": {"kind": "daiminkan"},
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=30,
                event={
                    "event_type": "call",
                    "seat": 2,
                    "call_kind": "kakan",
                    "meld": {"kind": "kakan"},
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

        records = list(extractor.extract(data))

        assert len(records) == 3
        assert records[0].values["is_kan"] is True
        assert records[1].values["is_kan"] is True
        assert records[2].values["is_kan"] is True

    def test_handles_missing_meld(self) -> None:
        """处理缺少 meld 的情况。"""
        extractor = CallExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=10,
                event={
                    "event_type": "call",
                    "seat": 0,
                    "call_kind": "pon",
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

        records = list(extractor.extract(data))

        assert len(records) == 1
        assert records[0].values["meld_type"] == ""


class TestFlowExtractor:
    """FlowExtractor 测试。"""

    def test_extracts_flow_events(self) -> None:
        """提取 flow 事件。"""
        extractor = FlowExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=50,
                event={
                    "event_type": "flow",
                    "flow_kind": "exhaustive_draw",
                    "tenpai_seats": [0, 2],
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

        records = list(extractor.extract(data))

        assert len(records) == 1
        r = records[0]
        assert r.kind == "flow"
        assert r.seat is None
        assert r.values["flow_kind"] == "exhaustive_draw"
        assert r.values["tenpai_seats"] == (0, 2)
        assert r.values["tenpai_count"] == 2

    def test_handles_empty_tenpai_seats(self) -> None:
        """处理空的 tenpai_seats。"""
        extractor = FlowExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=50,
                event={
                    "event_type": "flow",
                    "flow_kind": "exhaustive_draw",
                    "tenpai_seats": [],
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

        records = list(extractor.extract(data))

        assert records[0].values["tenpai_count"] == 0

    def test_tracks_hand_index(self) -> None:
        """追踪 hand_index。"""
        extractor = FlowExtractor()
        events = [
            EventRecord(
                match_id="m1",
                step_index=20,
                event={
                    "event_type": "flow",
                    "flow_kind": "exhaustive_draw",
                    "tenpai_seats": [1],
                },
            ),
            EventRecord(
                match_id="m1",
                step_index=25,
                event={"event_type": "hand_over", "winners": []},
            ),
            EventRecord(
                match_id="m1",
                step_index=50,
                event={
                    "event_type": "flow",
                    "flow_kind": "exhaustive_draw",
                    "tenpai_seats": [0, 1, 2, 3],
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

        records = list(extractor.extract(data))

        assert len(records) == 2
        assert records[0].hand_index == 0
        assert records[1].hand_index == 1


class TestExtractorProtocol:
    """测试 extractor 协议一致性。"""

    def test_all_extractors_have_name(self) -> None:
        """所有 extractor 都有 name 属性。"""
        extractors = [
            MatchEndExtractor(),
            HandOverExtractor(),
            DecisionExtractor(),
            RonExtractor(),
            TsumoExtractor(),
            RiichiExtractor(),
            CallExtractor(),
            FlowExtractor(),
        ]

        for ext in extractors:
            assert hasattr(ext, "name")
            assert isinstance(ext.name, str)
            assert len(ext.name) > 0

    def test_all_extractors_return_iterator(self) -> None:
        """所有 extractors 返回迭代器。"""
        extractor = MatchEndExtractor()
        data = RunData(
            match_id="m1",
            job_id="j1",
            seed=42,
            decisions=[],
            events=[],
            summary=None,
        )

        result = extractor.extract(data)

        # 应该是迭代器
        assert hasattr(result, "__iter__")

        # 可以转为 list
        records = list(result)
        assert isinstance(records, list)