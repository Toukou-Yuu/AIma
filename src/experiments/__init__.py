"""Experiments module: experiment config, runner, jobs."""

from experiments.job import JobRecord, JobSpec, JobState
from experiments.schema import (
    ArtifactSpec,
    ExperimentMetaSpec,
    ExperimentSpec,
    MatchSpec,
    RuleSpec,
    RuntimeSpec,
    SeedSpec,
)


def __getattr__(name: str):
    """Lazily expose ExperimentRunner without importing sinks during CLI startup."""
    if name == "ExperimentRunner":
        from experiments.runner import ExperimentRunner

        return ExperimentRunner
    raise AttributeError(name)

__all__ = [
    "ArtifactSpec",
    "ExperimentMetaSpec",
    "ExperimentRunner",
    "ExperimentSpec",
    "JobRecord",
    "JobSpec",
    "JobState",
    "MatchSpec",
    "RuleSpec",
    "RuntimeSpec",
    "SeedSpec",
]
