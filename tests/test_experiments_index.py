"""Tests for experiments.index module."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from experiments.index import (
    create_index,
    get_experiment,
    get_index_path,
    get_job,
    get_jobs_by_experiment,
    index_job_artifacts,
    insert_experiment,
    insert_job,
    insert_metrics_summary,
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

    def test_migrates_metrics_summary_primary_key_to_per_seat(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE metrics_summary (
                match_id TEXT PRIMARY KEY,
                final_points_json TEXT
            )
        """)
        cursor.execute(
            "INSERT INTO metrics_summary (match_id, final_points_json) VALUES (?, ?)",
            ("match_001", "[25000, 25000, 25000, 25000]"),
        )
        conn.commit()
        conn.close()

        create_index(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(metrics_summary)")
        pk_cols = [
            row[1]
            for row in sorted((row for row in cursor.fetchall() if row[5]), key=lambda row: row[5])
        ]
        conn.close()
        assert pk_cols == ["match_id", "seat"]

        insert_metrics_summary(db_path, "match_001", seat=0, final_score=32000)
        insert_metrics_summary(db_path, "match_001", seat=1, final_score=28000)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT seat, final_score, final_points_json
            FROM metrics_summary
            WHERE match_id = ?
            ORDER BY seat
            """,
            ("match_001",),
        )
        rows = cursor.fetchall()
        conn.close()

        assert [row[0] for row in rows] == [-1, 0, 1]
        assert rows[0][2] == "[25000, 25000, 25000, 25000]"


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

    def test_rebuilds_v4_job_metrics_and_artifact_paths(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "test_exp"
        job_dir = exp_dir / "jobs" / "job_001"
        job_dir.mkdir(parents=True)

        summary = {
            "schema_version": 1,
            "match_id": "match_001",
            "job_id": "job_001",
            "seed": 7,
            "preset": "tonpuu",
            "outcome": "completed",
            "final_phase": "MATCH_END",
            "hand_count": 4,
            "step_count": 80,
            "decision_count": 40,
            "event_count": 120,
            "duration_ms": 123.4,
        }
        metrics = {
            "schema_version": 1,
            "match_id": "match_001",
            "job_id": "job_001",
            "per_seat": [
                {"seat": 0, "final_points": 30000, "rank": 1, "fallback_count": 2},
                {"seat": 1, "final_points": 24000, "rank": 2, "fallback_count": 0},
            ],
        }
        (job_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (job_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (job_dir / "events.jsonl").write_text("", encoding="utf-8")
        (job_dir / "decisions.jsonl").write_text("", encoding="utf-8")
        (job_dir / "replay.json").write_text("{}", encoding="utf-8")

        stats = rebuild_index(tmp_path)

        assert stats["jobs"] == 1
        assert stats["matches"] == 1
        assert stats["metrics_summaries"] == 2
        assert stats["artifact_paths"] == 5

        db_path = get_index_path(tmp_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT seat, final_score, rank, fallback_count FROM metrics_summary ORDER BY seat"
        )
        metric_rows = cursor.fetchall()
        cursor.execute("SELECT artifact_type FROM artifact_paths ORDER BY artifact_type")
        artifact_types = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert metric_rows == [(0, 30000, 1, 2), (1, 24000, 2, 0)]
        assert artifact_types == ["decisions", "events", "metrics", "replay", "summary"]


class TestIndexJobArtifacts:
    def test_indexes_job_artifacts_from_source_files(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        create_index(db_path)
        job_dir = tmp_path / "job_001"
        job_dir.mkdir()

        summary = {
            "match_id": "match_001",
            "job_id": "job_001",
            "seed": 11,
            "preset": "hanchan",
            "outcome": "completed",
            "final_phase": "MATCH_END",
        }
        metrics = {
            "per_seat": [
                {"seat": 0, "final_points": 31000, "rank": 1},
                {"seat": 1, "final_points": 27000, "rank": 2},
                {"seat": 2, "final_points": 23000, "rank": 3},
                {"seat": 3, "final_points": 19000, "rank": 4},
            ]
        }
        (job_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (job_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (job_dir / "events.jsonl").write_text("", encoding="utf-8")
        (job_dir / "decisions.jsonl").write_text("", encoding="utf-8")
        (job_dir / "replay.json").write_text("{}", encoding="utf-8")

        counts = index_job_artifacts(
            db_path=db_path,
            experiment_id="test_exp",
            job_id="job_001",
            job_dir=job_dir,
            state="succeeded",
        )

        assert counts == {
            "jobs": 1,
            "matches": 1,
            "metrics_summaries": 4,
            "artifact_paths": 5,
        }

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM metrics_summary WHERE match_id = ?", ("match_001",))
        metrics_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM artifact_paths WHERE job_id = ?", ("job_001",))
        artifact_count = cursor.fetchone()[0]
        conn.close()

        assert metrics_count == 4
        assert artifact_count == 5
