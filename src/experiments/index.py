"""SQLite index for experiment tracking."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from experiments.schema import ExperimentSpec

ARTIFACT_FILES: dict[str, str] = {
    "summary": "summary.json",
    "metrics": "metrics.json",
    "replay": "replay.json",
    "events": "events.jsonl",
    "decisions": "decisions.jsonl",
}

METRICS_SUMMARY_COLUMNS = [
    "match_id",
    "seat",
    "final_points_json",
    "point_delta_json",
    "final_score",
    "rank",
    "win_count",
    "deal_in_count",
    "riichi_count",
    "fallback_count",
    "parse_error_count",
    "avg_latency_ms",
    "avg_prompt_tokens",
    "avg_completion_tokens",
]


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
                run_dir TEXT,
                rule_version TEXT,
                config_hash TEXT,
                status TEXT
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
                output_dir TEXT,
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
                preset TEXT,
                stopped_reason TEXT,
                final_phase TEXT,
                outcome TEXT,
                hand_count INTEGER,
                step_count INTEGER,
                decision_count INTEGER,
                event_count INTEGER,
                duration_ms REAL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
        """)

        # Create metrics_summary table (new in v4)
        _create_metrics_summary_table(cursor)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifact_paths (
                experiment_id TEXT,
                job_id TEXT,
                match_id TEXT,
                artifact_type TEXT,
                path TEXT,
                PRIMARY KEY (job_id, artifact_type),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
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

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_artifact_paths_job
            ON artifact_paths(job_id)
        """)

        _ensure_columns(cursor)
        _migrate_metrics_summary_primary_key(cursor)

        conn.commit()
    finally:
        conn.close()


def _create_metrics_summary_table(cursor: sqlite3.Cursor) -> None:
    """Create the current metrics_summary schema."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics_summary (
            match_id TEXT,
            seat INTEGER NOT NULL DEFAULT -1,
            final_points_json TEXT,
            point_delta_json TEXT,
            final_score INTEGER,
            rank INTEGER,
            win_count INTEGER,
            deal_in_count INTEGER,
            riichi_count INTEGER,
            fallback_count INTEGER,
            parse_error_count INTEGER,
            avg_latency_ms REAL,
            avg_prompt_tokens REAL,
            avg_completion_tokens REAL,
            PRIMARY KEY (match_id, seat),
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        )
    """)


def _ensure_columns(cursor: sqlite3.Cursor) -> None:
    """Best-effort schema migration for databases created by older versions."""
    migrations = {
        "experiments": {
            "rule_version": "TEXT",
            "config_hash": "TEXT",
            "status": "TEXT",
        },
        "jobs": {
            "output_dir": "TEXT",
        },
        "matches": {
            "preset": "TEXT",
            "stopped_reason": "TEXT",
            "event_count": "INTEGER",
            "duration_ms": "REAL",
        },
        "metrics_summary": {
            "seat": "INTEGER NOT NULL DEFAULT -1",
            "final_score": "INTEGER",
            "rank": "INTEGER",
            "win_count": "INTEGER",
            "deal_in_count": "INTEGER",
            "riichi_count": "INTEGER",
        },
    }
    for table, columns in migrations.items():
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for column, decl in columns.items():
            if column not in existing:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
                except sqlite3.OperationalError:
                    pass


def _migrate_metrics_summary_primary_key(cursor: sqlite3.Cursor) -> None:
    """Migrate old metrics_summary(match_id primary key) to per-seat primary key."""
    cursor.execute("PRAGMA table_info(metrics_summary)")
    rows = cursor.fetchall()
    pk_cols = [
        row[1]
        for row in sorted((row for row in rows if row[5]), key=lambda row: row[5])
    ]
    if pk_cols == ["match_id", "seat"]:
        return

    legacy_table = "metrics_summary_legacy_migration"
    cursor.execute(f"DROP TABLE IF EXISTS {legacy_table}")
    cursor.execute(f"ALTER TABLE metrics_summary RENAME TO {legacy_table}")
    _create_metrics_summary_table(cursor)

    legacy_cols = {row[1] for row in rows}
    select_exprs: list[str] = []
    insert_cols: list[str] = []
    for col in METRICS_SUMMARY_COLUMNS:
        if col not in legacy_cols:
            continue
        insert_cols.append(col)
        if col == "seat":
            select_exprs.append("COALESCE(seat, -1)")
        else:
            select_exprs.append(col)

    if insert_cols:
        cursor.execute(
            f"""
            INSERT OR REPLACE INTO metrics_summary ({", ".join(insert_cols)})
            SELECT {", ".join(select_exprs)}
            FROM {legacy_table}
            """
        )
    cursor.execute(f"DROP TABLE {legacy_table}")


def insert_experiment(
    db_path: str | Path,
    experiment_id: str,
    description: str,
    tags: list[str],
    created_at: str,
    config_path: str | None = None,
    run_dir: str | None = None,
    rule_version: str | None = None,
    config_hash: str | None = None,
    status: str | None = None,
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
            (id, description, tags, created_at, config_path, run_dir,
             rule_version, config_hash, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                description,
                json.dumps(tags),
                created_at,
                config_path,
                run_dir,
                rule_version,
                config_hash,
                status,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_experiment_status(
    db_path: str | Path,
    experiment_id: str,
    status: str,
    finished_at: str | None = None,
) -> None:
    """Update experiment status after completion.

    Args:
        db_path: Path to the SQLite database file.
        experiment_id: Unique identifier for the experiment.
        status: Final status ("succeeded", "failed", or "partial").
        finished_at: ISO format timestamp when experiment finished (optional).
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE experiments SET status = ? WHERE id = ?
            """,
            (status, experiment_id),
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
    output_dir: str | None = None,
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
            (job_id, experiment_id, seed, state, started_at, finished_at,
             match_id, error_message, output_dir)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                output_dir,
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
    output_dir: str | None = None,
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
    if output_dir is not None:
        updates.append("output_dir = ?")
        values.append(output_dir)

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
    preset: str | None = None,
    final_phase: str | None = None,
    outcome: str | None = None,
    stopped_reason: str | None = None,
    hand_count: int | None = 0,
    step_count: int | None = 0,
    decision_count: int | None = 0,
    event_count: int | None = None,
    duration_ms: float | None = None,
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
            (match_id, job_id, experiment_id, seed, preset, stopped_reason,
             final_phase, outcome, hand_count, step_count, decision_count,
             event_count, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                job_id,
                experiment_id,
                seed,
                preset,
                stopped_reason,
                final_phase,
                outcome,
                hand_count,
                step_count,
                decision_count,
                event_count,
                duration_ms,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_metrics_summary(
    db_path: str | Path,
    match_id: str,
    seat: int = -1,
    final_points: tuple[int, ...] | None = None,
    point_delta: tuple[int, ...] | None = None,
    final_score: int | None = None,
    rank: int | None = None,
    win_count: int = 0,
    deal_in_count: int = 0,
    riichi_count: int = 0,
    fallback_count: int = 0,
    parse_error_count: int = 0,
    avg_latency_ms: float | None = 0.0,
    avg_prompt_tokens: float | None = 0.0,
    avg_completion_tokens: float | None = 0.0,
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
            (match_id, seat, final_points_json, point_delta_json,
             final_score, rank, win_count, deal_in_count, riichi_count,
             fallback_count, parse_error_count, avg_latency_ms,
             avg_prompt_tokens, avg_completion_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                seat if seat is not None else -1,
                json.dumps(final_points) if final_points else None,
                json.dumps(point_delta) if point_delta else None,
                final_score,
                rank,
                win_count,
                deal_in_count,
                riichi_count,
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


def insert_artifact_path(
    db_path: str | Path,
    *,
    experiment_id: str,
    job_id: str,
    match_id: str,
    artifact_type: str,
    path: str,
) -> None:
    """Insert one artifact path into the rebuildable query index."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO artifact_paths
            (experiment_id, job_id, match_id, artifact_type, path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (experiment_id, job_id, match_id, artifact_type, path),
        )
        conn.commit()
    finally:
        conn.close()


def index_job_artifacts(
    db_path: str | Path,
    *,
    experiment_id: str,
    job_id: str,
    job_dir: str | Path,
    default_seed: int = 0,
    default_preset: str | None = None,
    state: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    error_message: str | None = None,
) -> dict[str, int]:
    """Index one v4 job directory from its artifact files.

    This is used by both runtime indexing and rebuild so SQLite remains a
    rebuildable query index over the same source-of-truth files.
    """
    job_dir = Path(job_dir)
    summary = _load_json(job_dir / ARTIFACT_FILES["summary"]) or {}
    metrics = _load_json(job_dir / ARTIFACT_FILES["metrics"]) or {}

    seed = int(summary.get("seed", default_seed))
    match_id = str(summary.get("match_id", job_id))
    preset = summary.get("preset", default_preset)
    outcome = summary.get("outcome")
    stopped_reason = summary.get("stopped_reason")

    indexed_state = state
    indexed_error = error_message
    if indexed_state is None:
        if summary.get("error") or outcome == "failed":
            indexed_state = "failed"
            indexed_error = str(summary.get("error") or stopped_reason or "failed")
        elif summary:
            indexed_state = "succeeded"
        else:
            indexed_state = "pending"

    insert_job(
        db_path=db_path,
        job_id=job_id,
        experiment_id=experiment_id,
        seed=seed,
        state=indexed_state,
        started_at=started_at,
        finished_at=finished_at,
        match_id=match_id,
        error_message=indexed_error,
        output_dir=str(job_dir),
    )

    counts = {"jobs": 1, "matches": 0, "metrics_summaries": 0, "artifact_paths": 0}

    if summary:
        insert_match(
            db_path=db_path,
            match_id=match_id,
            job_id=job_id,
            experiment_id=experiment_id,
            seed=seed,
            preset=preset,
            final_phase=summary.get("final_phase"),
            outcome=outcome,
            stopped_reason=stopped_reason,
            hand_count=summary.get("hand_count"),
            step_count=summary.get("step_count"),
            decision_count=summary.get("decision_count"),
            event_count=summary.get("event_count"),
            duration_ms=summary.get("duration_ms"),
        )
        counts["matches"] = 1

    per_seat = metrics.get("per_seat", [])
    if isinstance(per_seat, list):
        for seat_metrics in per_seat:
            if not isinstance(seat_metrics, dict):
                continue
            seat = int(seat_metrics.get("seat", -1))
            insert_metrics_summary(
                db_path=db_path,
                match_id=match_id,
                seat=seat,
                final_score=seat_metrics.get("final_score", seat_metrics.get("final_points")),
                rank=seat_metrics.get("rank"),
                win_count=seat_metrics.get("win_count", 0),
                deal_in_count=seat_metrics.get("deal_in_count", 0),
                riichi_count=seat_metrics.get("riichi_count", 0),
                fallback_count=seat_metrics.get("fallback_count", 0),
                parse_error_count=seat_metrics.get("parse_error_count", 0),
                avg_latency_ms=seat_metrics.get("avg_latency_ms"),
                avg_prompt_tokens=seat_metrics.get("avg_prompt_tokens"),
                avg_completion_tokens=seat_metrics.get("avg_completion_tokens"),
            )
            counts["metrics_summaries"] += 1

    for artifact_type, filename in ARTIFACT_FILES.items():
        artifact_path = job_dir / filename
        if artifact_path.exists():
            insert_artifact_path(
                db_path=db_path,
                experiment_id=experiment_id,
                job_id=job_id,
                match_id=match_id,
                artifact_type=artifact_type,
                path=str(artifact_path),
            )
            counts["artifact_paths"] += 1

    return counts


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON object from disk, returning None for missing/invalid files."""
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


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
            SELECT id, description, tags, created_at, config_path, run_dir,
                   rule_version, config_hash, status
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
            "rule_version": row[6],
            "config_hash": row[7],
            "status": row[8],
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
            SELECT job_id, experiment_id, seed, state, started_at, finished_at,
                   match_id, error_message, output_dir
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
            "output_dir": row[8],
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
                SELECT job_id, experiment_id, seed, state, started_at, finished_at,
                       match_id, error_message, output_dir
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
                "output_dir": row[8],
            }
            for row in rows
        ]
    finally:
        conn.close()


def _infer_experiment_status(job_states: list[str]) -> str:
    """Infer experiment status from job states.

    Args:
        job_states: List of job states.

    Returns:
        Inferred experiment status:
        - "succeeded" if all jobs succeeded
        - "failed" if all jobs failed
        - "partial" if mixed succeeded/failed
        - "indexed" if cannot determine
    """
    if not job_states:
        return "indexed"

    succeeded = sum(1 for s in job_states if s == "succeeded")
    failed = sum(1 for s in job_states if s == "failed")
    total = len(job_states)

    if succeeded == total:
        return "succeeded"
    elif failed == total:
        return "failed"
    elif succeeded > 0 and failed > 0:
        return "partial"
    else:
        return "indexed"


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
        "artifact_paths": 0,
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
        preset: str | None = None
        rule_version: str | None = None

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
                    preset = manifest.get("match", {}).get("preset")
                    rule_version = manifest.get("rules", {}).get("version")
                    config_path = str(manifest_yaml_path)
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
                preset = spec.match.preset
                rule_version = spec.rules.version
            except Exception as e:
                stats["errors"].append(
                    f"Failed to load config.yaml for {experiment_id}: {e}"
                )

        # Try to get created_at from directory metadata
        if not created_at:
            created_at = datetime.fromtimestamp(exp_dir.stat().st_ctime).isoformat()

        # Insert experiment record (status will be updated after scanning jobs)
        insert_experiment(
            db_path=db_path,
            experiment_id=experiment_id,
            description=description,
            tags=tags,
            created_at=created_at or datetime.now().isoformat(),
            config_path=config_path,
            run_dir=str(exp_dir),
            rule_version=rule_version,
            status="indexed",  # Temporary, will be updated after job scan
        )
        stats["experiments"] += 1

        # Track job states for experiment status inference
        job_states: list[str] = []

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
            state: str | None = None
            seed = 0
            started_at_job: str | None = None
            finished_at_job: str | None = None
            error_message: str | None = None

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

            indexed = index_job_artifacts(
                db_path=db_path,
                experiment_id=experiment_id,
                job_id=job_id,
                job_dir=job_dir,
                default_seed=seed,
                default_preset=preset,
                state=state,
                started_at=started_at_job,
                finished_at=finished_at_job,
                error_message=error_message,
            )
            stats["jobs"] += indexed["jobs"]
            stats["matches"] += indexed["matches"]
            stats["metrics_summaries"] += indexed["metrics_summaries"]
            stats["artifact_paths"] += indexed["artifact_paths"]

            # Track job state for experiment status inference
            job_states.append(state)

        # Update experiment status based on job states
        if job_states:
            exp_status = _infer_experiment_status(job_states)
            update_experiment_status(
                db_path=db_path,
                experiment_id=experiment_id,
                status=exp_status,
            )

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
