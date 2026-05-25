"""RunDataSource: read-only data source for UI viewer."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiments.index import get_experiment, get_index_path, get_jobs_by_experiment
from metrics.loader import RunData, load_single_job

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobInfo:
    """Lightweight job information for listing."""

    job_id: str
    experiment_id: str
    seed: int
    state: str
    match_id: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ExperimentInfo:
    """Lightweight experiment information for listing."""

    experiment_id: str
    description: str
    tags: tuple[str, ...]
    run_dir: str
    job_count: int = 0


class RunDataSource:
    """Read-only data source for run artifacts.

    Provides access to experiment and job data without writing to artifacts.
    Falls back to file scanning when SQLite index is unavailable.
    """

    def __init__(self, run_root: Path):
        """Initialize data source.

        Args:
            run_root: Root directory containing run artifacts (e.g., runs/)
        """
        self.run_root = Path(run_root)
        self._db_path = get_index_path(self.run_root)
        self._sqlite_available = self._check_sqlite()

    def _check_sqlite(self) -> bool:
        """Check if SQLite database is available.

        Returns:
            True if database exists and is readable, False otherwise.
        """
        if not self._db_path.exists():
            return False

        try:
            conn = sqlite3.connect(self._db_path)
            conn.close()
            return True
        except sqlite3.Error:
            logger.warning("SQLite database exists but cannot be opened: %s", self._db_path)
            return False

    def needs_rebuild(self) -> bool:
        """Check if the SQLite index needs to be rebuilt.

        Returns:
            True if index is missing or out of sync with run directories.
        """
        # If run root doesn't exist, nothing to rebuild
        if not self.run_root.exists():
            return False

        if not self._sqlite_available:
            return True

        # Check if any experiment directories are not in the index
        try:
            indexed_experiments = self._list_experiments_from_db()
            indexed_ids = {e.experiment_id for e in indexed_experiments}

            for exp_dir in self.run_root.iterdir():
                if not exp_dir.is_dir():
                    continue
                if exp_dir.name == "runs.db":
                    continue
                if exp_dir.name not in indexed_ids:
                    return True

            return False
        except Exception:
            return True

    def list_experiments(self) -> list[ExperimentInfo]:
        """List all available experiments.

        Returns:
            List of ExperimentInfo for all experiments.
        """
        if self._sqlite_available:
            try:
                return self._list_experiments_from_db()
            except Exception as e:
                logger.warning("Failed to read from SQLite, falling back to file scan: %s", e)

        return self._list_experiments_from_files()

    def _list_experiments_from_db(self) -> list[ExperimentInfo]:
        """List experiments from SQLite index.

        Returns:
            List of ExperimentInfo from database.
        """
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, description, tags, run_dir
                FROM experiments
                ORDER BY created_at DESC
                """
            )
            rows = cursor.fetchall()

            result: list[ExperimentInfo] = []
            for row in rows:
                exp_id = row[0]
                description = row[1] or ""
                tags = json.loads(row[2]) if row[2] else []
                run_dir = row[3] or str(self.run_root / exp_id)

                # Get job count
                cursor.execute(
                    "SELECT COUNT(*) FROM jobs WHERE experiment_id = ?",
                    (exp_id,),
                )
                job_count = cursor.fetchone()[0]

                result.append(
                    ExperimentInfo(
                        experiment_id=exp_id,
                        description=description,
                        tags=tuple(tags),
                        run_dir=run_dir,
                        job_count=job_count,
                    )
                )

            return result
        finally:
            conn.close()

    def _list_experiments_from_files(self) -> list[ExperimentInfo]:
        """List experiments by scanning run directories.

        Returns:
            List of ExperimentInfo from file system.
        """
        if not self.run_root.exists():
            return []

        result: list[ExperimentInfo] = []

        for exp_dir in self.run_root.iterdir():
            if not exp_dir.is_dir():
                continue
            if exp_dir.name == "runs.db":
                continue

            exp_id = exp_dir.name
            description = ""
            tags: list[str] = []

            # Try to load metadata from config or manifest
            config_path = exp_dir / "config.yaml"
            if config_path.exists():
                try:
                    from experiments.schema import ExperimentSpec

                    spec = ExperimentSpec.from_yaml(config_path)
                    exp_id = spec.experiment.id
                    description = spec.experiment.description
                    tags = spec.experiment.tags
                except Exception:
                    pass

            manifest_path = exp_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, encoding="utf-8") as f:
                        manifest = json.load(f)
                    if not description:
                        description = manifest.get("description", "")
                    if not tags:
                        tags = manifest.get("tags", [])
                except Exception:
                    pass

            # Count jobs (seed-* directories)
            job_count = sum(
                1 for d in exp_dir.iterdir() if d.is_dir() and d.name.startswith("seed-")
            )

            result.append(
                ExperimentInfo(
                    experiment_id=exp_id,
                    description=description,
                    tags=tuple(tags),
                    run_dir=str(exp_dir),
                    job_count=job_count,
                )
            )

        return result

    def get_jobs(self, experiment_id: str) -> list[JobInfo]:
        """Get all jobs for an experiment.

        Args:
            experiment_id: Experiment identifier.

        Returns:
            List of JobInfo for all jobs in the experiment.
        """
        if self._sqlite_available:
            try:
                return self._get_jobs_from_db(experiment_id)
            except Exception as e:
                logger.warning("Failed to read from SQLite, falling back to file scan: %s", e)

        return self._get_jobs_from_files(experiment_id)

    def _get_jobs_from_db(self, experiment_id: str) -> list[JobInfo]:
        """Get jobs from SQLite index.

        Args:
            experiment_id: Experiment identifier.

        Returns:
            List of JobInfo from database.
        """
        jobs_data = get_jobs_by_experiment(self._db_path, experiment_id)

        return [
            JobInfo(
                job_id=job["job_id"],
                experiment_id=job["experiment_id"],
                seed=job["seed"],
                state=job["state"],
                match_id=job.get("match_id"),
                error_message=job.get("error_message"),
            )
            for job in jobs_data
        ]

    def _get_jobs_from_files(self, experiment_id: str) -> list[JobInfo]:
        """Get jobs by scanning experiment directory.

        Args:
            experiment_id: Experiment identifier.

        Returns:
            List of JobInfo from file system.
        """
        exp_dir = self.run_root / experiment_id
        if not exp_dir.exists():
            return []

        result: list[JobInfo] = []

        for seed_dir in exp_dir.iterdir():
            if not seed_dir.is_dir():
                continue
            if not seed_dir.name.startswith("seed-"):
                continue

            try:
                seed = int(seed_dir.name.split("-", 1)[1])
            except ValueError:
                continue

            job_id = f"{experiment_id}_{seed_dir.name}"
            state = "pending"
            match_id: str | None = None
            error_message: str | None = None

            # Check summary.json for state
            summary_path = seed_dir / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, encoding="utf-8") as f:
                        summary = json.load(f)

                    if "error" in summary:
                        state = "failed"
                        if isinstance(summary["error"], dict):
                            error_message = summary["error"].get("message", str(summary["error"]))
                        else:
                            error_message = str(summary["error"])
                    elif "result" in summary:
                        state = "succeeded"

                    match_id = summary.get("match_id")
                except Exception:
                    pass

            # Check job.json for more accurate state
            job_json_path = seed_dir / "job.json"
            if job_json_path.exists():
                try:
                    with open(job_json_path, encoding="utf-8") as f:
                        job_data = json.load(f)

                    state = job_data.get("state", state)
                    match_id = job_data.get("match_id", match_id)
                    if job_data.get("error"):
                        error = job_data["error"]
                        error_message = json.dumps(error) if isinstance(error, dict) else str(error)
                except Exception:
                    pass

            result.append(
                JobInfo(
                    job_id=job_id,
                    experiment_id=experiment_id,
                    seed=seed,
                    state=state,
                    match_id=match_id,
                    error_message=error_message,
                )
            )

        # Sort by seed
        result.sort(key=lambda j: j.seed)
        return result

    def load_job(self, job_id: str) -> RunData | None:
        """Load complete data for a single job.

        Args:
            job_id: Job identifier (format: {experiment_id}_seed-{seed}).

        Returns:
            RunData if job exists, None otherwise.
        """
        # Parse job_id to get experiment_id and seed_dir
        parts = job_id.rsplit("_seed-", 1)
        if len(parts) != 2:
            logger.warning("Invalid job_id format: %s", job_id)
            return None

        experiment_id = parts[0]
        seed_str = parts[1]

        # Find job directory
        exp_dir = self.run_root / experiment_id
        job_dir = exp_dir / f"seed-{seed_str}"

        if not job_dir.exists():
            return None

        try:
            seed = int(seed_str)
        except ValueError:
            seed = 0

        return load_single_job(job_dir, job_id, seed)

    def get_metrics(self, experiment_id: str) -> dict[str, Any]:
        """Get aggregated metrics for an experiment.

        Args:
            experiment_id: Experiment identifier.

        Returns:
            Dictionary containing:
            - total_jobs: Total number of jobs
            - succeeded: Number of succeeded jobs
            - failed: Number of failed jobs
            - pending: Number of pending jobs
            - running: Number of running jobs
            - skipped: Number of skipped jobs
            - avg_duration_ms: Average duration in milliseconds (if available)
        """
        jobs = self.get_jobs(experiment_id)

        total = len(jobs)
        if total == 0:
            return {
                "total_jobs": 0,
                "succeeded": 0,
                "failed": 0,
                "pending": 0,
                "running": 0,
                "skipped": 0,
                "avg_duration_ms": None,
            }

        state_counts: dict[str, int] = {}
        for job in jobs:
            state_counts[job.state] = state_counts.get(job.state, 0) + 1

        # Calculate average duration from succeeded jobs
        durations: list[float] = []
        for job in jobs:
            if job.state != "succeeded":
                continue
            run_data = self.load_job(job.job_id)
            if run_data and run_data.summary and run_data.summary.duration_ms:
                durations.append(run_data.summary.duration_ms)

        avg_duration = sum(durations) / len(durations) if durations else None

        return {
            "total_jobs": total,
            "succeeded": state_counts.get("succeeded", 0),
            "failed": state_counts.get("failed", 0),
            "pending": state_counts.get("pending", 0),
            "running": state_counts.get("running", 0),
            "skipped": state_counts.get("skipped", 0),
            "avg_duration_ms": avg_duration,
        }