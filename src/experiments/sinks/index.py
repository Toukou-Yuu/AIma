"""IndexSink: SQLite index writer for experiment jobs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from experiments.index import index_job_artifacts, insert_job

if TYPE_CHECKING:
    from arena.match_result import MatchResult
    from arena.policy import DecisionContext, PolicyDecision
    from arena.result import EngineStepResult


class IndexSink:
    """EventSink that updates SQLite job index.

    Creates initial job record on construction and updates state on match end.
    """

    def __init__(
        self,
        db_path: str | Path,
        job_id: str,
        experiment_id: str,
        seed: int,
        started_at: str | None = None,
        job_dir: str | Path | None = None,
        preset: str | None = None,
    ) -> None:
        """Initialize IndexSink and create initial job record.

        Args:
            db_path: Path to the SQLite database file.
            job_id: Unique identifier for the job.
            experiment_id: ID of the parent experiment.
            seed: Random seed used for the job.
            started_at: ISO format timestamp when job started (optional).
        """
        self._db_path = Path(db_path)
        self._job_id = job_id
        self._experiment_id = experiment_id
        self._seed = seed
        self._started_at = started_at
        self._job_dir = Path(job_dir) if job_dir is not None else None
        self._preset = preset

        # Create initial job record with "running" state
        insert_job(
            db_path=self._db_path,
            job_id=job_id,
            experiment_id=experiment_id,
            seed=seed,
            state="running",
            started_at=started_at,
            output_dir=str(self._job_dir) if self._job_dir else None,
        )

    def on_step(
        self,
        ctx: "DecisionContext",
        decision: "PolicyDecision",
        result: "EngineStepResult",
    ) -> None:
        """Called on each step. No-op for IndexSink.

        Args:
            ctx: Decision context.
            decision: Policy decision result.
            result: Engine step result.
        """
        # IndexSink does not track per-step data
        pass

    def on_match_end(self, result: "MatchResult") -> None:
        """Called when match ends. Updates job record in SQLite.

        Args:
            result: Complete match result.
        """
        state = "failed" if result.outcome == "failed" else "succeeded"
        error_message = result.stopped_reason if state == "failed" else None

        if self._job_dir is None:
            insert_job(
                db_path=self._db_path,
                job_id=self._job_id,
                experiment_id=self._experiment_id,
                seed=self._seed,
                state=state,
                started_at=self._started_at,
                match_id=result.match_id,
                error_message=error_message,
            )
            return

        index_job_artifacts(
            db_path=self._db_path,
            experiment_id=self._experiment_id,
            job_id=self._job_id,
            job_dir=self._job_dir,
            default_seed=self._seed,
            default_preset=self._preset,
            state=state,
            started_at=self._started_at,
            error_message=error_message,
        )
