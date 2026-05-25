"""Artifact契约测试 - 验证smoke实验产物结构完整性。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def smoke_run_dir() -> Path:
    """smoke实验运行目录。"""
    return Path("runs/smoke")


@pytest.fixture
def llm_run_dir() -> Path:
    """LLM实验运行目录。"""
    return Path("runs/llm_pipeline_test")


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