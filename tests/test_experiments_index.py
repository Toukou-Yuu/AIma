"""Tests for experiments.index module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.index import (
    create_index,
    get_index_path,
    get_experiment,
    get_job,
    get_jobs_by_experiment,
    insert_experiment,
    insert_job,
    rebuild_index,
    update_job,
)


class TestGetIndexPath:
    def test_string_input(self) -> None:
        path = get_index_path("runs")
        assert path == Path("runs/runs.db")

    def test_path_input(self) -> None:
        path = get_index_path(Path("/tmp/experiments"))
        assert path == Path("/tmp/experiments/runs.db")


class TestCreateIndex:
    def test_creates_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check experiments table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='experiments'"
        )
        assert cursor.fetchone() is not None

        # Check jobs table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        )
        assert cursor.fetchone() is not None

        # Check indexes exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_jobs_experiment'"
        )
        assert cursor.fetchone() is not None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_jobs_state'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "test.db"
        create_index(db_path)
        assert db_path.parent.exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)
        create_index(db_path)  # Should not raise
        assert db_path.exists()


class TestInsertExperiment:
    def test_inserts_record(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test experiment",
            tags=["smoke", "v4"],
            created_at="2026-05-25T10:00:00",
            config_path="/path/to/config.yaml",
            run_dir="/path/to/runs/test_exp",
        )

        record = get_experiment(db_path, "test_exp")
        assert record is not None
        assert record["id"] == "test_exp"
        assert record["description"] == "Test experiment"
        assert record["tags"] == ["smoke", "v4"]
        assert record["created_at"] == "2026-05-25T10:00:00"
        assert record["config_path"] == "/path/to/config.yaml"
        assert record["run_dir"] == "/path/to/runs/test_exp"

    def test_insert_or_replace(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Original",
            tags=["original"],
            created_at="2026-05-25T10:00:00",
        )

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Updated",
            tags=["updated"],
            created_at="2026-05-25T11:00:00",
        )

        record = get_experiment(db_path, "test_exp")
        assert record is not None
        assert record["description"] == "Updated"
        assert record["tags"] == ["updated"]

    def test_empty_tags(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        record = get_experiment(db_path, "test_exp")
        assert record is not None
        assert record["tags"] == []


class TestInsertJob:
    def test_inserts_record(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            experiment_id="test_exp",
            seed=1,
            state="running",
            started_at="2026-05-25T10:01:00",
        )

        record = get_job(db_path, "test_exp_seed-0001")
        assert record is not None
        assert record["job_id"] == "test_exp_seed-0001"
        assert record["experiment_id"] == "test_exp"
        assert record["seed"] == 1
        assert record["state"] == "running"
        assert record["started_at"] == "2026-05-25T10:01:00"

    def test_all_states(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        # "pending" | "running" | "succeeded" | "failed" | "skipped"
        for state in ["pending", "running", "succeeded", "failed", "skipped"]:
            insert_job(
                db_path=db_path,
                job_id=f"test_exp_seed-{state}",
                experiment_id="test_exp",
                seed=ord(state[0]),
                state=state,
            )

            record = get_job(db_path, f"test_exp_seed-{state}")
            assert record is not None
            assert record["state"] == state

    def test_with_error_message(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            experiment_id="test_exp",
            seed=1,
            state="failed",
            error_message="Connection timeout",
        )

        record = get_job(db_path, "test_exp_seed-0001")
        assert record is not None
        assert record["error_message"] == "Connection timeout"


class TestUpdateJob:
    def test_updates_state(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            experiment_id="test_exp",
            seed=1,
            state="running",
            started_at="2026-05-25T10:01:00",
        )

        update_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            state="succeeded",
            finished_at="2026-05-25T10:02:00",
        )

        record = get_job(db_path, "test_exp_seed-0001")
        assert record is not None
        assert record["state"] == "succeeded"
        assert record["finished_at"] == "2026-05-25T10:02:00"

    def test_updates_match_id(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            experiment_id="test_exp",
            seed=1,
            state="running",
        )

        update_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            match_id="match_abc123",
        )

        record = get_job(db_path, "test_exp_seed-0001")
        assert record is not None
        assert record["match_id"] == "match_abc123"

    def test_no_update_if_no_params(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            experiment_id="test_exp",
            seed=1,
            state="running",
        )

        update_job(db_path=db_path, job_id="test_exp_seed-0001")

        record = get_job(db_path, "test_exp_seed-0001")
        assert record is not None
        assert record["state"] == "running"


class TestGetJobsByExperiment:
    def test_returns_jobs_ordered_by_seed(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0003",
            experiment_id="test_exp",
            seed=3,
            state="succeeded",
        )
        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0001",
            experiment_id="test_exp",
            seed=1,
            state="succeeded",
        )
        insert_job(
            db_path=db_path,
            job_id="test_exp_seed-0002",
            experiment_id="test_exp",
            seed=2,
            state="running",
        )

        jobs = get_jobs_by_experiment(db_path, "test_exp")
        assert len(jobs) == 3
        assert jobs[0]["seed"] == 1
        assert jobs[1]["seed"] == 2
        assert jobs[2]["seed"] == 3

    def test_returns_empty_list_if_no_jobs(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)

        insert_experiment(
            db_path=db_path,
            experiment_id="test_exp",
            description="Test",
            tags=[],
            created_at="2026-05-25T10:00:00",
        )

        jobs = get_jobs_by_experiment(db_path, "test_exp")
        assert jobs == []


class TestRebuildIndex:
    def test_empty_directory(self, tmp_path: Path) -> None:
        stats = rebuild_index(tmp_path)
        assert stats["experiments"] == 0
        assert stats["jobs"] == 0
        assert stats["errors"] == []

    def test_rebuilds_from_job_json(self, tmp_path: Path) -> None:
        # Create experiment directory structure
        exp_dir = tmp_path / "test_exp"
        exp_dir.mkdir()

        # Create config.yaml
        config_content = """
experiment:
  id: test_exp
  description: Test experiment
  tags: [smoke, v4]
rules:
  version: v3.1.3
seeds:
  start: 0
  count: 1
match:
  preset: hanchan
policies:
  seat0:
    type: first_legal
    id: p0
"""
        (exp_dir / "config.yaml").write_text(config_content.strip())

        # Create seed directory with job.json
        seed_dir = exp_dir / "seed-0001"
        seed_dir.mkdir()

        job_json = {
            "schema_version": 1,
            "job_id": "test_exp_seed-0001",
            "experiment_id": "test_exp",
            "seed": 1,
            "state": "succeeded",
            "started_at": "2026-05-25T10:00:00",
            "finished_at": "2026-05-25T10:01:00",
            "match_id": "match_001",
        }
        (seed_dir / "job.json").write_text(json.dumps(job_json))

        stats = rebuild_index(tmp_path)
        assert stats["experiments"] == 1
        assert stats["jobs"] == 1

        # Verify records
        db_path = get_index_path(tmp_path)
        exp_record = get_experiment(db_path, "test_exp")
        assert exp_record is not None
        assert exp_record["description"] == "Test experiment"
        assert exp_record["tags"] == ["smoke", "v4"]

        job_record = get_job(db_path, "test_exp_seed-0001")
        assert job_record is not None
        assert job_record["state"] == "succeeded"
        assert job_record["match_id"] == "match_001"

    def test_rebuilds_from_summary_json(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "test_exp"
        exp_dir.mkdir()

        seed_dir = exp_dir / "seed-0001"
        seed_dir.mkdir()

        # summary.json without job.json
        summary = {
            "schema_version": 1,
            "match_id": "match_001",
            "result": "completed",
        }
        (seed_dir / "summary.json").write_text(json.dumps(summary))

        stats = rebuild_index(tmp_path)
        assert stats["jobs"] == 1

        db_path = get_index_path(tmp_path)
        job_record = get_job(db_path, "test_exp_seed-0001")
        assert job_record is not None
        assert job_record["state"] == "succeeded"

    def test_handles_failed_job(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "test_exp"
        exp_dir.mkdir()

        seed_dir = exp_dir / "seed-0001"
        seed_dir.mkdir()

        job_json = {
            "schema_version": 1,
            "job_id": "test_exp_seed-0001",
            "experiment_id": "test_exp",
            "seed": 1,
            "state": "failed",
            "error": {"message": "Connection timeout"},
        }
        (seed_dir / "job.json").write_text(json.dumps(job_json))

        stats = rebuild_index(tmp_path)
        assert stats["jobs"] == 1

        db_path = get_index_path(tmp_path)
        job_record = get_job(db_path, "test_exp_seed-0001")
        assert job_record is not None
        assert job_record["state"] == "failed"

    def test_recreates_database(self, tmp_path: Path) -> None:
        db_path = get_index_path(tmp_path)
        create_index(db_path)

        # Insert some existing data
        insert_experiment(
            db_path=db_path,
            experiment_id="old_exp",
            description="Old experiment",
            tags=["old"],
            created_at="2026-05-25T10:00:00",
        )

        # Create new experiment directory
        exp_dir = tmp_path / "new_exp"
        exp_dir.mkdir()

        seed_dir = exp_dir / "seed-0001"
        seed_dir.mkdir()

        job_json = {
            "schema_version": 1,
            "job_id": "new_exp_seed-0001",
            "experiment_id": "new_exp",
            "seed": 1,
            "state": "succeeded",
        }
        (seed_dir / "job.json").write_text(json.dumps(job_json))

        stats = rebuild_index(tmp_path)
        assert stats["experiments"] == 1  # Only new_exp
        assert stats["jobs"] == 1

        # Old experiment should not exist
        old_record = get_experiment(db_path, "old_exp")
        assert old_record is None