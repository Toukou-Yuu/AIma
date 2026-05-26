"""Artifact契约测试 - 验证smoke实验产物结构完整性。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def smoke_run_dir() -> Path:
    """smoke实验运行目录。"""
    # v4 layout: runs/{output}/{experiment_id}/
    return Path("runs/smoke/smoke")


@pytest.fixture
def llm_run_dir() -> Path:
    """LLM实验运行目录。"""
    return Path("runs/llm_pipeline_test")


@pytest.fixture
def smoke_job_dir(smoke_run_dir: Path) -> Path:
    """smoke实验的job目录。"""
    jobs_dir = smoke_run_dir / "jobs"
    job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
    assert job_dirs, "jobs目录下无job子目录"
    return job_dirs[0]


# ============================================================================
# P0-4 回归测试：summary.json 字段完整性
# ============================================================================

SUMMARY_REQUIRED_FIELDS = [
    "schema_version",
    "match_id",
    "job_id",
    "seed",
    "step_count",
    "stopped_reason",
    "outcome",
    "final_phase",
    "decision_count",
    "event_count",
    "hand_count",
    "final_points",
    "rank",
    "duration_ms",
]

METRICS_REQUIRED_KEYS = ["per_match", "per_seat"]


class TestSummaryJsonFields:
    """P0-4回归测试：验证summary.json包含所有必需字段。"""

    def test_summary_has_all_required_fields(self, smoke_job_dir: Path) -> None:
        """summary.json必须包含所有契约定义的字段。

        Regression test for P0-4: Artifact契约不完整
        - Bug: summary.json缺少 final_phase, decision_count, event_count,
               hand_count, final_points, rank, duration_ms
        - Fix: 在 ArtifactWriter.on_match_end() 中补充字段
        """
        summary_path = smoke_job_dir / "summary.json"
        assert summary_path.exists(), f"{smoke_job_dir.name}/summary.json不存在"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        missing_fields = [field for field in SUMMARY_REQUIRED_FIELDS if field not in summary]

        assert not missing_fields, (
            f"summary.json缺少必需字段: {missing_fields}. "
            f"现有字段: {list(summary.keys())}"
        )

    def test_summary_field_types(self, smoke_job_dir: Path) -> None:
        """summary.json字段类型正确。"""
        summary_path = smoke_job_dir / "summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        # schema_version 应为整数
        assert isinstance(summary.get("schema_version"), int), "schema_version应为整数"

        # 计数字段应为非负整数
        for field in ["decision_count", "event_count", "hand_count", "step_count"]:
            value = summary.get(field)
            assert isinstance(value, int), f"{field}应为整数，实际为{type(value)}"
            assert value >= 0, f"{field}应为非负整数，实际为{value}"

        # final_phase 应为字符串
        assert isinstance(summary.get("final_phase"), str), "final_phase应为字符串"

        # final_points 应为4元素列表
        final_points = summary.get("final_points")
        assert isinstance(final_points, list), "final_points应为列表"
        assert len(final_points) == 4, f"final_points应有4个元素，实际为{len(final_points)}"

        # rank 应为4元素列表
        rank = summary.get("rank")
        assert isinstance(rank, list), "rank应为列表"
        assert len(rank) == 4, f"rank应有4个元素，实际为{len(rank)}"

        # duration_ms 应为非负数
        duration_ms = summary.get("duration_ms")
        assert isinstance(duration_ms, (int, float)), "duration_ms应为数值"
        assert duration_ms >= 0, f"duration_ms应为非负数，实际为{duration_ms}"

    def test_summary_decision_count_matches_file(self, smoke_job_dir: Path) -> None:
        """summary.json的decision_count与decisions.jsonl行数一致。"""
        summary_path = smoke_job_dir / "summary.json"
        decisions_path = smoke_job_dir / "decisions.jsonl"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        if "decision_count" not in summary:
            pytest.fail("decision_count字段缺失，无法验证一致性")

        with open(decisions_path, encoding="utf-8") as f:
            actual_count = sum(1 for _ in f)

        assert summary["decision_count"] == actual_count, (
            f"decision_count不一致: summary={summary['decision_count']}, "
            f"decisions.jsonl行数={actual_count}"
        )

    def test_summary_event_count_matches_file(self, smoke_job_dir: Path) -> None:
        """summary.json的event_count与events.jsonl行数一致。"""
        summary_path = smoke_job_dir / "summary.json"
        events_path = smoke_job_dir / "events.jsonl"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        if "event_count" not in summary:
            pytest.fail("event_count字段缺失，无法验证一致性")

        with open(events_path, encoding="utf-8") as f:
            actual_count = sum(1 for _ in f)

        assert summary["event_count"] == actual_count, (
            f"event_count不一致: summary={summary['event_count']}, "
            f"events.jsonl行数={actual_count}"
        )

    def test_summary_final_phase_matches_replay(self, smoke_job_dir: Path) -> None:
        """summary.json的final_phase与replay.json一致。"""
        summary_path = smoke_job_dir / "summary.json"
        replay_path = smoke_job_dir / "replay.json"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        with open(replay_path, encoding="utf-8") as f:
            replay = json.load(f)

        if "final_phase" not in summary:
            pytest.fail("final_phase字段缺失，无法验证一致性")

        assert summary["final_phase"] == replay.get("final_phase"), (
            f"final_phase不一致: summary={summary['final_phase']}, "
            f"replay={replay.get('final_phase')}"
        )


class TestMetricsJson:
    """P0-4回归测试：验证metrics.json存在且结构正确。"""

    def test_metrics_json_exists(self, smoke_job_dir: Path) -> None:
        """每个job目录必须有metrics.json。

        Regression test for P0-4: metrics.json不生成
        - Bug: ArtifactWriter未生成metrics.json
        - Fix: 在 on_match_end() 中新增metrics.json写入逻辑
        """
        metrics_path = smoke_job_dir / "metrics.json"
        assert metrics_path.exists(), f"{smoke_job_dir.name}/metrics.json不存在"

    def test_metrics_json_structure(self, smoke_job_dir: Path) -> None:
        """metrics.json包含per_match和per_seat结构。"""
        metrics_path = smoke_job_dir / "metrics.json"

        if not metrics_path.exists():
            pytest.fail("metrics.json不存在，无法验证结构")

        with open(metrics_path, encoding="utf-8") as f:
            metrics = json.load(f)

        missing_keys = [key for key in METRICS_REQUIRED_KEYS if key not in metrics]
        assert not missing_keys, f"metrics.json缺少必需键: {missing_keys}"

    def test_metrics_per_match_structure(self, smoke_job_dir: Path) -> None:
        """metrics.json的per_match结构正确。"""
        metrics_path = smoke_job_dir / "metrics.json"

        if not metrics_path.exists():
            pytest.fail("metrics.json不存在")

        with open(metrics_path, encoding="utf-8") as f:
            metrics = json.load(f)

        if "per_match" not in metrics:
            pytest.fail("metrics.json缺少per_match键")

        per_match = metrics["per_match"]
        assert isinstance(per_match, dict), "per_match应为对象"

    def test_metrics_per_seat_structure(self, smoke_job_dir: Path) -> None:
        """metrics.json的per_seat结构正确。"""
        metrics_path = smoke_job_dir / "metrics.json"

        if not metrics_path.exists():
            pytest.fail("metrics.json不存在")

        with open(metrics_path, encoding="utf-8") as f:
            metrics = json.load(f)

        if "per_seat" not in metrics:
            pytest.fail("metrics.json缺少per_seat键")

        per_seat = metrics["per_seat"]
        assert isinstance(per_seat, list), "per_seat应为列表"
        assert len(per_seat) == 4, f"per_seat应有4个元素，实际为{len(per_seat)}"


class TestArtifactContract:
    """验证artifact契约。"""

    def test_manifest_exists(self, smoke_run_dir: Path) -> None:
        """manifest.yaml存在。"""
        manifest_path = smoke_run_dir / "manifest.yaml"
        assert manifest_path.exists(), "manifest.yaml不存在"

    def test_jobs_jsonl_exists(self, smoke_run_dir: Path) -> None:
        """jobs.jsonl存在且有数据。"""
        jobs_path = smoke_run_dir / "jobs.jsonl"
        assert jobs_path.exists(), "jobs.jsonl不存在"

        with open(jobs_path, encoding="utf-8") as f:
            content = f.read()
        assert content.strip(), "jobs.jsonl为空"

    def test_jobs_directory_structure(self, smoke_run_dir: Path) -> None:
        """jobs/<job_id>/目录结构完整。"""
        jobs_dir = smoke_run_dir / "jobs"
        assert jobs_dir.exists(), "jobs目录不存在"

        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "jobs目录下无job子目录"

    def test_summary_json_exists(self, smoke_run_dir: Path) -> None:
        """每个job有summary.json。"""
        jobs_dir = smoke_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]

        for job_dir in job_dirs:
            summary_path = job_dir / "summary.json"
            assert summary_path.exists(), f"{job_dir.name}/summary.json不存在"

    def test_decisions_jsonl_exists(self, smoke_run_dir: Path) -> None:
        """每个job有decisions.jsonl。"""
        jobs_dir = smoke_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]

        for job_dir in job_dirs:
            decisions_path = job_dir / "decisions.jsonl"
            assert decisions_path.exists(), f"{job_dir.name}/decisions.jsonl不存在"

    def test_events_jsonl_exists(self, smoke_run_dir: Path) -> None:
        """每个job有events.jsonl。"""
        jobs_dir = smoke_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]

        for job_dir in job_dirs:
            events_path = job_dir / "events.jsonl"
            assert events_path.exists(), f"{job_dir.name}/events.jsonl不存在"


class TestIDConsistency:
    """验证ID一致性。"""

    def test_jobs_jsonl_matches_summary(self, smoke_run_dir: Path) -> None:
        """jobs.jsonl中的job_id与summary.json一致。"""
        jobs_path = smoke_run_dir / "jobs.jsonl"
        with open(jobs_path, encoding="utf-8") as f:
            job_record = json.loads(f.read())

        jobs_dir = smoke_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1

        job_dir = job_dirs[0]
        summary_path = job_dir / "summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        assert job_record["job_id"] == summary["job_id"], "job_id不一致"


class TestMetricsContract:
    """验证metrics契约。"""

    def test_reliability_summary_has_total_decisions(self, smoke_run_dir: Path) -> None:
        """reliability_summary.json有total_decisions。"""
        aggregate_dir = smoke_run_dir / "aggregate"
        if not aggregate_dir.exists():
            pytest.skip("aggregate目录不存在")

        reliability_path = aggregate_dir / "reliability_summary.json"
        if not reliability_path.exists():
            pytest.skip("reliability_summary.json不存在")

        with open(reliability_path, encoding="utf-8") as f:
            reliability = json.load(f)

        assert "total_decisions" in reliability
        assert reliability["total_decisions"] > 0, "total_decisions应为正数"


class TestLLMPipelineContract:
    """验证LLM策略的AgentPipeline契约。"""

    def test_llm_decisions_have_diagnostics(self, llm_run_dir: Path) -> None:
        """LLM策略的decisions有完整diagnostics。"""
        if not llm_run_dir.exists():
            pytest.skip("llm_pipeline_test运行目录不存在")

        jobs_dir = llm_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        if not job_dirs:
            pytest.skip("无job目录")

        decisions_path = job_dirs[0] / "decisions.jsonl"
        if not decisions_path.exists():
            pytest.skip("decisions.jsonl不存在")

        with open(decisions_path, encoding="utf-8") as f:
            first_line = f.readline()

        decision = json.loads(first_line)
        diagnostics = decision.get("diagnostics", {})

        # 只检查seat=0的决策（LLM策略）
        if decision.get("seat") == 0:
            assert diagnostics, "seat=0应有diagnostics"
            assert "messages" in diagnostics, "diagnostics应有messages"
            assert "prompt_template" in diagnostics, "diagnostics应有prompt_template"


class TestSQLiteContract:
    """验证SQLite index契约。"""

    def test_sqlite_tables_exist(self) -> None:
        """runs.db有必需表。"""
        import sqlite3

        db_path = Path("runs/runs.db")
        if not db_path.exists():
            pytest.skip("runs.db不存在")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        required_tables = {"experiments", "jobs", "matches", "metrics_summary"}
        for table in required_tables:
            assert table in tables, f"缺少表: {table}"

    def test_sqlite_has_data(self) -> None:
        """runs.db有数据。"""
        import sqlite3

        db_path = Path("runs/runs.db")
        if not db_path.exists():
            pytest.skip("runs.db不存在")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM experiments")
        exp_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs")
        job_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM matches")
        match_count = cursor.fetchone()[0]

        conn.close()

        assert exp_count >= 1, "experiments表应有数据"
        assert job_count >= 1, "jobs表应有数据"
        assert match_count >= 1, "matches表应有数据"