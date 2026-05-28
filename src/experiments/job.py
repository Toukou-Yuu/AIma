"""Job model for experiment execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from experiments.schema import MatchSpec


class JobState(StrEnum):
    """Job execution state."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class JobSpec:
    """Specification for a single job execution.

    Attributes:
        job_id: Unique job identifier
        experiment_id: Parent experiment identifier
        seed: Random seed for this job
        match_spec: Match configuration (reference, not copied)
        match_index: Zero-based match index in the experiment seed plan
    """

    job_id: str
    experiment_id: str
    seed: int
    match_spec: "MatchSpec"
    match_index: int = 0


@dataclass
class JobRecord:
    """Record of job execution state."""

    job_id: str
    experiment_id: str
    seed: int
    state: JobState
    started_at: str | None = None
    finished_at: str | None = None
    match_id: str | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with schema version.

        Returns:
            Dictionary representation with schema_version field.
        """
        d = {"schema_version": 1, **asdict(self), "state": str(self.state)}
        if self.error:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "JobRecord":
        """Create JobRecord from dictionary.

        Args:
            d: Dictionary containing job record data.

        Returns:
            JobRecord instance.
        """
        return cls(
            job_id=d["job_id"],
            experiment_id=d["experiment_id"],
            seed=d["seed"],
            state=JobState(d["state"]),
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            match_id=d.get("match_id"),
            error=d.get("error"),
        )
