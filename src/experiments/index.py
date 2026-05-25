"""SQLite index for experiment tracking."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from experiments.job import JobRecord, JobState
from experiments.schema import ExperimentSpec


def get_index_path(output_root: str | Path) -> Path:
    """Get the path to the runs.db SQLite database.

    Args:
        output_root: Root directory for run outputs.

    Returns:
        Path to the runs.db file.
    """
    return Path(output_root) / "runs.db"


def create_index(db_path: str | Path) -> None:
    """Create the SQLite index schema.

    Args:
        db_path: Path to the SQLite database file.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Create experiments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                description TEXT,
                tags TEXT,
                created_at TEXT,
                config_path TEXT,
                run_dir TEXT
            )
        """)

        # Create jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                experiment_id TEXT,
                seed INTEGER,
                state TEXT,
                started_at TEXT,
                finished_at TEXT,
                match_id TEXT,
                error_message TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_experiment
            ON jobs(experiment_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_state
            ON jobs(state)
        """)

        conn.commit()
    finally:
        conn.close()


def insert_experiment(
    db_path: str | Path,
    experiment_id: str,
    description: str,
    tags: list[str],
    created_at: str,
    config_path: str | None = None,
    run_dir: str | None = None,
) -> None:
    """Insert an experiment record into the database.

    Args:
        db_path: Path to the SQLite database file.
        experiment_id: Unique identifier for the experiment.
        description: Human-readable description.
        tags: List of tags for categorization.
        created_at: ISO format timestamp.
        config_path: Path to the configuration file (optional).
        run_dir: Path to the run directory (optional).
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO experiments
            (id, description, tags, created_at, config_path, run_dir)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                description,
                json.dumps(tags),
                created_at,
                config_path,
                run_dir,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_job(
    db_path: str | Path,
    job_id: str,
    experiment_id: str,
    seed: int,
    state: str,  # "pending" | "running" | "succeeded" | "failed" | "skipped"
    started_at: str | None = None,
    finished_at: str | None = None,
    match_id: str | None = None,
    error_message: str | None = None,
) -> None:
    """Insert a job record into the database.

    Args:
        db_path: Path to the SQLite database file.
        job_id: Unique identifier for the job.
        experiment_id: ID of the parent experiment.
        seed: Random seed used for the job.
        state: Current state of the job.
        started_at: ISO format timestamp when job started (optional).
        finished_at: ISO format timestamp when job finished (optional).
        match_id: ID of the match (optional).
        error_message: Error message if job failed (optional).
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO jobs
            (job_id, experiment_id, seed, state, started_at, finished_at, match_id, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                experiment_id,
                seed,
                state,
                started_at,
                finished_at,
                match_id,
                error_message,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_job(
    db_path: str | Path,
    job_id: str,
    state: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    match_id: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update a job record in the database.

    Args:
        db_path: Path to the SQLite database file.
        job_id: Unique identifier for the job.
        state: New state of the job (optional).
        started_at: ISO format timestamp when job started (optional).
        finished_at: ISO format timestamp when job finished (optional).
        match_id: ID of the match (optional).
        error_message: Error message if job failed (optional).
    """
    updates: list[str] = []
    values: list[Any] = []

    if state is not None:
        updates.append("state = ?")
        values.append(state)
    if started_at is not None:
        updates.append("started_at = ?")
        values.append(started_at)
    if finished_at is not None:
        updates.append("finished_at = ?")
        values.append(finished_at)
    if match_id is not None:
        updates.append("match_id = ?")
        values.append(match_id)
    if error_message is not None:
        updates.append("error_message = ?")
        values.append(error_message)

    if not updates:
        return

    values.append(job_id)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?
            """,
            values,
        )
        conn.commit()
    finally:
        conn.close()


def get_experiment(db_path: str | Path, experiment_id: str) -> dict[str, Any] | None:
    """Get an experiment record from the database.

    Args:
        db_path: Path to the SQLite database file.
        experiment_id: Unique identifier for the experiment.

    Returns:
        Experiment record as dictionary, or None if not found.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, description, tags, created_at, config_path, run_dir
            FROM experiments WHERE id = ?
            """,
            (experiment_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "description": row[1],
            "tags": json.loads(row[2]) if row[2] else [],
            "created_at": row[3],
            "config_path": row[4],
            "run_dir": row[5],
        }
    finally:
        conn.close()


def get_job(db_path: str | Path, job_id: str) -> dict[str, Any] | None:
    """Get a job record from the database.

    Args:
        db_path: Path to the SQLite database file.
        job_id: Unique identifier for the job.

    Returns:
        Job record as dictionary, or None if not found.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT job_id, experiment_id, seed, state, started_at, finished_at, match_id, error_message
            FROM jobs WHERE job_id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "job_id": row[0],
            "experiment_id": row[1],
            "seed": row[2],
            "state": row[3],
            "started_at": row[4],
            "finished_at": row[5],
            "match_id": row[6],
            "error_message": row[7],
        }
    finally:
        conn.close()


def get_jobs_by_experiment(
    db_path: str | Path,
    experiment_id: str,
) -> list[dict[str, Any]]:
    """Get all job records for an experiment.

    Args:
        db_path: Path to the SQLite database file.
        experiment_id: Unique identifier for the experiment.

    Returns:
        List of job records as dictionaries.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT job_id, experiment_id, seed, state, started_at, finished_at, match_id, error_message
            FROM jobs WHERE experiment_id = ?
            ORDER BY seed
            """,
            (experiment_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "job_id": row[0],
                "experiment_id": row[1],
                "seed": row[2],
                "state": row[3],
                "started_at": row[4],
                "finished_at": row[5],
                "match_id": row[6],
                "error_message": row[7],
            }
            for row in rows
        ]
    finally:
        conn.close()


def rebuild_index(output_root: str | Path) -> dict[str, Any]:
    """Rebuild the SQLite index by scanning the runs directory.

    Args:
        output_root: Root directory for run outputs.

    Returns:
        Dictionary with rebuild statistics:
        - experiments: Number of experiments indexed
        - jobs: Number of jobs indexed
        - errors: List of error messages
    """
    output_root = Path(output_root)
    db_path = get_index_path(output_root)

    # Create or recreate the index
    if db_path.exists():
        db_path.unlink()
    create_index(db_path)

    stats: dict[str, Any] = {
        "experiments": 0,
        "jobs": 0,
        "errors": [],
    }

    # Scan for experiment directories
    if not output_root.exists():
        return stats

    for exp_dir in output_root.iterdir():
        if not exp_dir.is_dir():
            continue
        if exp_dir.name == "runs.db":
            continue

        experiment_id = exp_dir.name
        config_path: str | None = None
        description = ""
        tags: list[str] = []
        created_at: str | None = None

        # Try to load experiment spec from config
        config_file = exp_dir / "config.yaml"
        if config_file.exists():
            config_path = str(config_file)
            try:
                spec = ExperimentSpec.from_yaml(config_file)
                experiment_id = spec.experiment.id
                description = spec.experiment.description
                tags = spec.experiment.tags
            except Exception as e:
                stats["errors"].append(
                    f"Failed to load config for {experiment_id}: {e}"
                )

        # Try to get created_at from directory metadata or manifest
        manifest_path = exp_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                created_at = manifest.get("created_at")
                if not description:
                    description = manifest.get("description", "")
                if not tags:
                    tags = manifest.get("tags", [])
            except Exception as e:
                stats["errors"].append(
                    f"Failed to load manifest for {experiment_id}: {e}"
                )

        if not created_at:
            created_at = datetime.fromtimestamp(exp_dir.stat().st_ctime).isoformat()

        # Insert experiment record
        insert_experiment(
            db_path=db_path,
            experiment_id=experiment_id,
            description=description,
            tags=tags,
            created_at=created_at or datetime.now().isoformat(),
            config_path=config_path,
            run_dir=str(exp_dir),
        )
        stats["experiments"] += 1

        # Scan for job directories (seed-NNNN format)
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

            # Try to load job state from summary.json
            state = "pending"  # Default state
            started_at_job: str | None = None
            finished_at_job: str | None = None
            match_id: str | None = None
            error_message: str | None = None

            summary_path = seed_dir / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, encoding="utf-8") as f:
                        summary = json.load(f)

                    # Check for error
                    if "error" in summary:
                        state = "failed"
                        if isinstance(summary["error"], dict):
                            error_message = summary["error"].get("message", str(summary["error"]))
                        else:
                            error_message = str(summary["error"])
                    elif "result" in summary:
                        state = "succeeded"

                    match_id = summary.get("match_id")
                    started_at_job = summary.get("started_at")
                    finished_at_job = summary.get("finished_at")
                except Exception as e:
                    stats["errors"].append(
                        f"Failed to load summary for {job_id}: {e}"
                    )

            # Check job.json for more accurate state
            job_json_path = seed_dir / "job.json"
            if job_json_path.exists():
                try:
                    with open(job_json_path, encoding="utf-8") as f:
                        job_data = json.load(f)
                    job_record = JobRecord.from_dict(job_data)
                    state = str(job_record.state)
                    started_at_job = job_record.started_at
                    finished_at_job = job_record.finished_at
                    match_id = job_record.match_id
                    if job_record.error:
                        error_message = json.dumps(job_record.error)
                except Exception as e:
                    stats["errors"].append(
                        f"Failed to load job.json for {job_id}: {e}"
                    )

            insert_job(
                db_path=db_path,
                job_id=job_id,
                experiment_id=experiment_id,
                seed=seed,
                state=state,
                started_at=started_at_job,
                finished_at=finished_at_job,
                match_id=match_id,
                error_message=error_message,
            )
            stats["jobs"] += 1

    return stats