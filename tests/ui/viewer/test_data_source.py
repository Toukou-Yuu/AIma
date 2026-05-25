"""Tests for ui.viewer.data_source module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ui.viewer.data_source import ExperimentInfo, JobInfo, RunDataSource


class TestRunDataSource:
    """Tests for RunDataSource class."""

    def test_init_with_nonexistent_path(self, tmp_path: Path) -> None:
        """RunDataSource should handle nonexistent paths gracefully."""
        nonexistent = tmp_path / "nonexistent"
        ds = RunDataSource(nonexistent)

        assert ds.run_root == nonexistent
        assert not ds.needs_rebuild()

    def test_list_experiments_empty(self, tmp_path: Path) -> None:
        """list_experiments should return empty list for empty directory."""
        ds = RunDataSource(tmp_path)
        result = ds.list_experiments()
        assert result == []

    def test_get_jobs_empty(self, tmp_path: Path) -> None:
        """get_jobs should return empty list for nonexistent experiment."""
        ds = RunDataSource(tmp_path)
        result = ds.get_jobs("nonexistent_experiment")
        assert result == []

    def test_load_job_invalid_id(self, tmp_path: Path) -> None:
        """load_job should return None for invalid job_id format."""
        ds = RunDataSource(tmp_path)
        result = ds.load_job("invalid_job_id")
        assert result is None

    def test_load_job_nonexistent(self, tmp_path: Path) -> None:
        """load_job should return None for nonexistent job."""
        ds = RunDataSource(tmp_path)
        result = ds.load_job("exp_seed-0")
        assert result is None

    def test_get_metrics_empty_experiment(self, tmp_path: Path) -> None:
        """get_metrics should return zeros for nonexistent experiment."""
        ds = RunDataSource(tmp_path)
        result = ds.get_metrics("nonexistent_experiment")
        assert result["total_jobs"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0

    def test_list_experiments_from_files(self, tmp_path: Path) -> None:
        """list_experiments should find experiment directories."""
        # Create experiment directory with seed subdirectory
        exp_dir = tmp_path / "test_exp"
        seed_dir = exp_dir / "seed-0"
        seed_dir.mkdir(parents=True)

        ds = RunDataSource(tmp_path)
        result = ds.list_experiments()

        assert len(result) == 1
        assert result[0].experiment_id == "test_exp"
        assert result[0].job_count == 1

    def test_get_jobs_from_files(self, tmp_path: Path) -> None:
        """get_jobs should find job directories."""
        # Create experiment directory with seed subdirectory
        exp_dir = tmp_path / "test_exp"
        seed_dir = exp_dir / "seed-42"
        seed_dir.mkdir(parents=True)

        # Create summary.json
        summary = {
            "match_id": "test-match",
            "result": "completed",
            "final_points": [25000, 25000, 25000, 25000],
        }
        import json

        with open(seed_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f)

        ds = RunDataSource(tmp_path)
        result = ds.get_jobs("test_exp")

        assert len(result) == 1
        assert result[0].job_id == "test_exp_seed-42"
        assert result[0].seed == 42
        assert result[0].state == "succeeded"

    def test_sqlite_fallback(self, tmp_path: Path) -> None:
        """RunDataSource should fallback to file scanning when SQLite unavailable."""
        # Create experiment directory
        exp_dir = tmp_path / "test_exp"
        seed_dir = exp_dir / "seed-0"
        seed_dir.mkdir(parents=True)

        # Force no SQLite
        ds = RunDataSource(tmp_path)
        ds._sqlite_available = False

        result = ds.list_experiments()
        assert len(result) == 1
        assert result[0].experiment_id == "test_exp"


class TestExperimentInfo:
    """Tests for ExperimentInfo dataclass."""

    def test_frozen(self) -> None:
        """ExperimentInfo should be immutable."""
        info = ExperimentInfo(
            experiment_id="test",
            description="Test experiment",
            tags=("tag1", "tag2"),
            run_dir="/path/to/run",
            job_count=5,
        )

        with pytest.raises(AttributeError):
            info.experiment_id = "modified"  # type: ignore[misc]


class TestJobInfo:
    """Tests for JobInfo dataclass."""

    def test_frozen(self) -> None:
        """JobInfo should be immutable."""
        info = JobInfo(
            job_id="test_seed-0",
            experiment_id="test",
            seed=0,
            state="succeeded",
        )

        with pytest.raises(AttributeError):
            info.state = "failed"  # type: ignore[misc]