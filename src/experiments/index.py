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

        # Create matches table (new in v4)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                job_id TEXT,
                experiment_id TEXT,
                seed INTEGER,
                final_phase TEXT,
                outcome TEXT,
                hand_count INTEGER,
                step_count INTEGER,
                decision_count INTEGER,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
        """)

        # Create metrics_summary table (new in v4)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_summary (
                match_id TEXT PRIMARY KEY,
                final_points_json TEXT,
                point_delta_json TEXT,
                fallback_count INTEGER,
                parse_error_count INTEGER,
                avg_latency_ms REAL,
                avg_prompt_tokens REAL,
                avg_completion_tokens REAL,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            )
        """)

        # Create index for matches
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_experiment
            ON matches(experiment_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_job
            ON matches(job_id)
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


def insert_match(
    db_path: str | Path,
    match_id: str,
    job_id: str,
    experiment_id: str,
    seed: int,
    final_phase: str | None = None,
    outcome: str | None = None,
    hand_count: int = 0,
    step_count: int = 0,
    decision_count: int = 0,
) -> None:
    """Insert a match record into the database.

    Args:
        db_path: Path to the SQLite database file.
        match_id: Unique identifier for the match (same as job_id in v4).
        job_id: ID of the parent job.
        experiment_id: ID of the parent experiment.
        seed: Random seed used for the match.
        final_phase: Final game phase (e.g., "FLOWN", "HAND_OVER").
        outcome: Match outcome (e.g., "completed", "flowout").
        hand_count: Number of hands played.
        step_count: Total number of steps.
        decision_count: Total number of decisions made.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO matches
            (match_id, job_id, experiment_id, seed, final_phase, outcome,
             hand_count, step_count, decision_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                job_id,
                experiment_id,
                seed,
                final_phase,
                outcome,
                hand_count,
                step_count,
                decision_count,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_metrics_summary(
    db_path: str | Path,
    match_id: str,
    final_points: tuple[int, ...] | None = None,
    point_delta: tuple[int, ...] | None = None,
    fallback_count: int = 0,
    parse_error_count: int = 0,
    avg_latency_ms: float = 0.0,
    avg_prompt_tokens: float = 0.0,
    avg_completion_tokens: float = 0.0,
) -> None:
    """Insert a metrics summary record into the database.

    Args:
        db_path: Path to the SQLite database file.
        match_id: Unique identifier for the match.
        final_points: Final points tuple for all 4 seats.
        point_delta: Point delta tuple for all 4 seats.
        fallback_count: Number of fallback decisions.
        parse_error_count: Number of parse errors.
        avg_latency_ms: Average decision latency in ms.
        avg_prompt_tokens: Average prompt tokens per decision.
        avg_completion_tokens: Average completion tokens per decision.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO metrics_summary
            (match_id, final_points_json, point_delta_json,
             fallback_count, parse_error_count, avg_latency_ms,
             avg_prompt_tokens, avg_completion_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                json.dumps(final_points) if final_points else None,
                json.dumps(point_delta) if point_delta else None,
                fallback_count,
                parse_error_count,
                avg_latency_ms,
                avg_prompt_tokens,
                avg_completion_tokens,
            ),
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
        "matches": 0,
        "metrics_summaries": 0,
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

        # Try to load experiment spec from manifest.yaml (v4 layout)
        manifest_yaml_path = exp_dir / "manifest.yaml"
        if manifest_yaml_path.exists():
            try:
                import yaml
                with open(manifest_yaml_path, encoding="utf-8") as f:
                    manifest = yaml.safe_load(f)
                if manifest:
                    experiment_id = manifest.get("experiment", {}).get("id", experiment_id)
                    description = manifest.get("experiment", {}).get("description", "")
                    tags = manifest.get("experiment", {}).get("tags", [])
            except Exception as e:
                stats["errors"].append(
                    f"Failed to load manifest.yaml for {experiment_id}: {e}"
                )

        # Also try config.yaml (for tests and old layout)
        config_yaml_path = exp_dir / "config.yaml"
        if config_yaml_path.exists() and not description:
            try:
                spec = ExperimentSpec.from_yaml(config_yaml_path)
                experiment_id = spec.experiment.id
                description = spec.experiment.description
                tags = spec.experiment.tags
                config_path = str(config_yaml_path)
            except Exception as e:
                stats["errors"].append(
                    f"Failed to load config.yaml for {experiment_id}: {e}"
                )

        # Try to get created_at from directory metadata
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

        # Scan for job directories (v4 layout: jobs/<job_id>/)
        jobs_dir = exp_dir / "jobs"
        if not jobs_dir.exists():
            # Fall back to old layout (seed-NNNN format)
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

                # Load job state from job.json first (most authoritative)
                state = "pending"
                started_at_job: str | None = None
                finished_at_job: str | None = None
                match_id_job: str | None = None
                error_message: str | None = None

                job_json_path = seed_dir / "job.json"
                if job_json_path.exists():
                    try:
                        with open(job_json_path, encoding="utf-8") as f:
                            job_data = json.load(f)
                        state = job_data.get("state", state)
                        started_at_job = job_data.get("started_at")
                        finished_at_job = job_data.get("finished_at")
                        match_id_job = job_data.get("match_id")
                        if job_data.get("error"):
                            err = job_data["error"]
                            if isinstance(err, dict):
                                error_message = err.get("message", str(err))
                            else:
                                error_message = str(err)
                    except Exception as e:
                        stats["errors"].append(f"Failed to load job.json for {job_id}: {e}")

                # Also check summary.json for additional info
                summary_path = seed_dir / "summary.json"
                if summary_path.exists():
                    try:
                        with open(summary_path, encoding="utf-8") as f:
                            summary = json.load(f)
                        if "error" in summary and state == "pending":
                            state = "failed"
                        elif "result" in summary and state == "pending":
                            state = "succeeded"
                        elif "step_count" in summary and state == "pending":
                            state = "succeeded"
                    except Exception as e:
                        stats["errors"].append(f"Failed to load summary for {job_id}: {e}")

                insert_job(
                    db_path=db_path,
                    job_id=job_id,
                    experiment_id=experiment_id,
                    seed=seed,
                    state=state,
                    started_at=started_at_job,
                    finished_at=finished_at_job,
                    match_id=match_id_job,
                    error_message=error_message,
                )
                stats["jobs"] += 1
            continue

        # v4 layout: jobs/<job_id>/
        for job_dir in jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue

            job_id = job_dir.name

            # Load job state from summary.json
            state = "pending"
            seed = 0
            started_at_job: str | None = None
            finished_at_job: str | None = None
            match_id: str | None = None
            error_message: str | None = None
            final_phase: str | None = None
            outcome: str | None = None
            hand_count: int = 0
            step_count: int = 0
            decision_count: int = 0

            summary_path = job_dir / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, encoding="utf-8") as f:
                        summary = json.load(f)

                    seed = summary.get("seed", 0)
                    match_id = summary.get("match_id", job_id)
                    step_count = summary.get("step_count", 0)
                    stopped_reason = summary.get("stopped_reason")

                    if stopped_reason:
                        state = "failed"
                        error_message = stopped_reason
                        outcome = "error"
                    else:
                        state = "succeeded"
                        outcome = "completed"

                    # Count decisions from decisions.jsonl
                    decisions_path = job_dir / "decisions.jsonl"
                    if decisions_path.exists():
                        decision_count = 0
                        with open(decisions_path, encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    decision_count += 1

                    # Estimate hand_count from step_count (roughly 20-30 steps per hand)
                    hand_count = step_count // 25

                    # Try to get final_phase from events.jsonl
                    events_path = job_dir / "events.jsonl"
                    if events_path.exists():
                        # Read last event
                        last_event: dict[str, Any] | None = None
                        with open(events_path, encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    try:
                                        last_event = json.loads(line)
                                    except json.JSONDecodeError:
                                        pass
                        if last_event:
                            event_data = last_event.get("event", {})
                            final_phase = event_data.get("phase")
                except Exception as e:
                    stats["errors"].append(f"Failed to load summary for {job_id}: {e}")

            # Also check jobs.jsonl for job records
            jobs_jsonl_path = exp_dir / "jobs.jsonl"
            if jobs_jsonl_path.exists():
                try:
                    with open(jobs_jsonl_path, encoding="utf-8") as f:
                        for line in f:
                            if not line.strip():
                                continue
                            record = json.loads(line)
                            if record.get("job_id") == job_id:
                                state = record.get("state", state)
                                started_at_job = record.get("started_at")
                                finished_at_job = record.get("finished_at")
                                seed = record.get("seed", seed)
                                if record.get("error"):
                                    error_obj = record.get("error")
                                    if isinstance(error_obj, dict):
                                        error_message = error_obj.get("message", str(error_obj))
                                    else:
                                        error_message = str(error_obj)
                                break
                except Exception as e:
                    stats["errors"].append(f"Failed to load jobs.jsonl: {e}")

            # Insert job record
            insert_job(
                db_path=db_path,
                job_id=job_id,
                experiment_id=experiment_id,
                seed=seed,
                state=state,
                started_at=started_at_job,
                finished_at=finished_at_job,
                match_id=match_id or job_id,
                error_message=error_message,
            )
            stats["jobs"] += 1

            # Insert match record
            insert_match(
                db_path=db_path,
                match_id=match_id or job_id,
                job_id=job_id,
                experiment_id=experiment_id,
                seed=seed,
                final_phase=final_phase,
                outcome=outcome,
                hand_count=hand_count,
                step_count=step_count,
                decision_count=decision_count,
            )
            stats["matches"] += 1

            # Load metrics from aggregate/reliability_summary.json
            aggregate_dir = exp_dir / "aggregate"
            reliability_path = aggregate_dir / "reliability_summary.json"
            if reliability_path.exists():
                try:
                    with open(reliability_path, encoding="utf-8") as f:
                        reliability = json.load(f)

                    # Get counts
                    fallback_count = reliability.get("parse_fallback_count", 0)
                    parse_error_count = reliability.get("parse_error_count", 0)
                    avg_latency_ms = reliability.get("avg_latency_ms", 0.0)
                    avg_prompt_tokens = reliability.get("avg_prompt_tokens", 0.0)
                    avg_completion_tokens = reliability.get("avg_completion_tokens", 0.0)

                    insert_metrics_summary(
                        db_path=db_path,
                        match_id=match_id or job_id,
                        fallback_count=fallback_count,
                        parse_error_count=parse_error_count,
                        avg_latency_ms=avg_latency_ms,
                        avg_prompt_tokens=avg_prompt_tokens,
                        avg_completion_tokens=avg_completion_tokens,
                    )
                    stats["metrics_summaries"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to load metrics for {job_id}: {e}")

    return stats


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Rebuild SQLite index for experiment runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m experiments.index --rebuild runs
        """,
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild SQLite index from existing run directories",
    )
    parser.add_argument(
        "output_root",
        type=Path,
        nargs="?",
        help="Output root directory (default: runs)",
        default=Path("runs"),
    )

    args = parser.parse_args()

    if not args.rebuild:
        parser.print_help()
        sys.exit(1)

    print(f"Rebuilding index for {args.output_root}...")
    stats = rebuild_index(args.output_root)

    print(f"Indexed {stats['experiments']} experiments, {stats['jobs']} jobs")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
        for error in stats["errors"]:
            print(f"  - {error}")
        sys.exit(1)

    sys.exit(0)