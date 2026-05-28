"""Metrics loader: load raw data from run directories."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class JobSummary:
    """Summary data for a single job/match."""

    match_id: str
    job_id: str
    seed: int
    outcome: str
    step_count: int
    hand_count: int
    final_points: tuple[int, int, int, int]
    point_delta: tuple[int, int, int, int]
    starting_points: tuple[int, int, int, int]
    duration_ms: float | None = None
    stopped_reason: str | None = None


@dataclass
class DecisionRecord:
    """Single decision record loaded from decisions.jsonl."""

    match_id: str
    step_index: int
    seat: int
    action: dict[str, Any]
    parse_status: str
    fallback_used: bool
    latency_ms: float | None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    hand_index: int | None = None


@dataclass
class EventRecord:
    """Single event record loaded from events.jsonl."""

    match_id: str
    step_index: int
    event: dict[str, Any]


@dataclass
class RunData:
    """Data loaded for a single run/job."""

    match_id: str
    job_id: str
    seed: int
    decisions: list[DecisionRecord]
    events: list[EventRecord]
    summary: JobSummary | None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL file into list of dicts."""
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError:
                continue
    return records


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON file into dict."""
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _parse_decision(record: dict[str, Any]) -> DecisionRecord:
    """Parse decision record from raw dict."""
    action = record.get("action", {})
    if hasattr(action, "to_dict"):
        action = action.to_dict()
    elif not isinstance(action, dict):
        action = {}

    return DecisionRecord(
        match_id=str(record.get("match_id", "")),
        step_index=int(record.get("step_index", 0)),
        hand_index=(
            int(record["hand_index"]) if record.get("hand_index") is not None else None
        ),
        seat=int(record.get("seat", 0)),
        action=action,
        parse_status=str(record.get("parse_status", "ok")),
        fallback_used=bool(record.get("fallback_used", False)),
        latency_ms=float(record.get("latency_ms", 0.0)) if record.get("latency_ms") is not None else None,
        diagnostics=record.get("diagnostics", {}),
    )


def _parse_event(record: dict[str, Any]) -> EventRecord:
    """Parse event record from raw dict."""
    event = record.get("event", {})
    if not isinstance(event, dict):
        event = {}

    return EventRecord(
        match_id=str(record.get("match_id", "")),
        step_index=int(record.get("step_index", 0)),
        event=event,
    )


def _parse_summary(data: dict[str, Any], job_id: str, seed: int) -> JobSummary:
    """Parse summary.json into JobSummary."""
    final_points_raw = data.get("final_points", [25000, 25000, 25000, 25000])
    final_points = tuple(int(p) for p in final_points_raw)

    point_delta_raw = data.get("point_delta", [0, 0, 0, 0])
    point_delta = tuple(int(p) for p in point_delta_raw)

    starting_points_raw = data.get("starting_points", [25000, 25000, 25000, 25000])
    starting_points = tuple(int(p) for p in starting_points_raw)

    return JobSummary(
        match_id=str(data.get("match_id", job_id)),
        job_id=job_id,
        seed=seed,
        outcome=str(data.get("outcome", "completed")),
        step_count=int(data.get("step_count", 0)),
        hand_count=int(data.get("hand_count", 0)),
        final_points=final_points,
        point_delta=point_delta,
        starting_points=starting_points,
        duration_ms=float(data.get("duration_ms", 0.0)) if data.get("duration_ms") is not None else None,
        stopped_reason=data.get("stopped_reason"),
    )


def load_single_job(job_dir: Path, job_id: str, seed: int) -> RunData:
    """Load data for a single job directory.

    Args:
        job_dir: Path to job directory (e.g., runs/{exp}/jobs/{job_id})
        job_id: Job identifier
        seed: Seed value for this job

    Returns:
        RunData containing all loaded records.
    """
    decisions_path = job_dir / "decisions.jsonl"
    events_path = job_dir / "events.jsonl"
    summary_path = job_dir / "summary.json"

    decision_dicts = _load_jsonl(decisions_path)
    decisions = [_parse_decision(d) for d in decision_dicts]

    event_dicts = _load_jsonl(events_path)
    events = [_parse_event(e) for e in event_dicts]

    summary_data = _load_json(summary_path)
    summary = _parse_summary(summary_data or {}, job_id, seed) if summary_data else None

    match_id = summary.match_id if summary else job_id

    return RunData(
        match_id=match_id,
        job_id=job_id,
        seed=seed,
        decisions=decisions,
        events=events,
        summary=summary,
    )


def load_run_data(run_dir: Path) -> list[RunData]:
    """Load all job data from a run directory.

    Args:
        run_dir: Path to run directory (e.g., runs/{experiment_id})

    Returns:
        List of RunData for all jobs in the run.
    """
    jobs_path = run_dir / "jobs.jsonl"
    jobs_dir = run_dir / "jobs"

    if not jobs_path.exists() and not jobs_dir.exists():
        return []

    # Load jobs.jsonl to get job_id -> seed mapping
    job_records = _load_jsonl(jobs_path)
    job_map: dict[str, int] = {}
    for record in job_records:
        job_id = str(record.get("job_id", ""))
        seed = int(record.get("seed", 0))
        job_map[job_id] = seed

    # If jobs.jsonl missing, scan jobs directory
    if not job_map and jobs_dir.exists():
        for job_subdir in jobs_dir.iterdir():
            if job_subdir.is_dir():
                job_id = job_subdir.name
                job_map[job_id] = 0

    # Load each job
    run_data: list[RunData] = []
    for job_id, seed in job_map.items():
        job_dir = jobs_dir / job_id
        if job_dir.exists():
            data = load_single_job(job_dir, job_id, seed)
            run_data.append(data)

    return run_data
