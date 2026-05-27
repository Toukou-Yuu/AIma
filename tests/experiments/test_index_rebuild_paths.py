"""Path semantics for experiments.index rebuild."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from experiments.index import get_index_path, rebuild_index


def _write_v4_run(output_root: Path, exp_id: str, *, seed: int = 1) -> Path:
    run_dir = output_root / exp_id
    job_id = f"{exp_id}_seed{seed:04d}_match0000"
    job_dir = run_dir / "jobs" / job_id
    job_dir.mkdir(parents=True)

    (run_dir / "manifest.yaml").write_text(
        f"""
experiment:
  id: {exp_id}
  description: {exp_id}
  tags: [test]
rules:
  version: v3.1.3
match:
  preset: tonpuu
""".strip(),
        encoding="utf-8",
    )
    (run_dir / "aggregate").mkdir()
    (job_dir / "summary.json").write_text(
        json.dumps(
            {
                "match_id": job_id,
                "job_id": job_id,
                "seed": seed,
                "preset": "tonpuu",
                "outcome": "completed",
                "final_phase": "match_end",
                "hand_count": 4,
                "step_count": 10,
                "decision_count": 4,
                "event_count": 8,
            }
        ),
        encoding="utf-8",
    )
    (job_dir / "metrics.json").write_text(
        json.dumps({"per_seat": [{"seat": 0, "final_points": 30000, "rank": 1}]}),
        encoding="utf-8",
    )
    for filename in ("events.jsonl", "decisions.jsonl"):
        (job_dir / filename).write_text("", encoding="utf-8")
    (job_dir / "replay.json").write_text("{}", encoding="utf-8")
    return run_dir


def _experiment_ids(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM experiments ORDER BY id")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def test_rebuild_output_root_indexes_all_experiments(tmp_path: Path) -> None:
    _write_v4_run(tmp_path, "exp_a", seed=1)
    _write_v4_run(tmp_path, "exp_b", seed=2)

    stats = rebuild_index(tmp_path)

    assert stats["experiments"] == 2
    assert stats["jobs"] == 2
    assert _experiment_ids(get_index_path(tmp_path)) == ["exp_a", "exp_b"]


def test_rebuild_single_run_dir_indexes_only_that_experiment(tmp_path: Path) -> None:
    run_a = _write_v4_run(tmp_path, "exp_a", seed=1)
    _write_v4_run(tmp_path, "exp_b", seed=2)

    stats = rebuild_index(run_a)

    assert stats["experiments"] == 1
    assert stats["jobs"] == 1
    assert _experiment_ids(get_index_path(run_a)) == ["exp_a"]


def test_rebuild_missing_path_raises_clear_error(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"

    with pytest.raises(FileNotFoundError, match="Rebuild path does not exist"):
        rebuild_index(missing)


def test_rebuild_cli_help_documents_output_root_or_run_dir() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [sys.executable, "-m", "experiments.index", "--help"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "Output root directory or a single experiment run directory" in result.stdout
