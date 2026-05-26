"""Tests for experiments.runner."""

from __future__ import annotations

from experiments.runner import ExperimentRunner
from experiments.schema import (
    ArtifactSpec,
    ExperimentMetaSpec,
    ExperimentSpec,
    MatchSpec,
    RuleSpec,
    SeedSpec,
)
from policies.schema import PolicySpec


def test_generate_job_spec_preserves_match_index(tmp_path) -> None:
    spec = ExperimentSpec(
        experiment=ExperimentMetaSpec(id="exp"),
        rules=RuleSpec(version="v3.1.3"),
        seeds=SeedSpec(explicit=[10, 20]),
        match=MatchSpec(preset="tonpuu"),
        artifacts=ArtifactSpec(output_root=str(tmp_path), sqlite_index=False),
        policies={
            f"seat{seat}": PolicySpec(type="first_legal", id=f"p{seat}")
            for seat in range(4)
        },
    )
    runner = ExperimentRunner(spec)

    job = runner._generate_job_spec(seed=20, match_index=1)

    assert job.match_index == 1
    assert job.job_id == "exp_seed0020_match0001"
