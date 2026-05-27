"""Experiment configuration schemas using Pydantic v2."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from policies.schema import PolicySpec


class ExperimentMetaSpec(BaseModel):
    """Experiment metadata."""

    id: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class RuleSpec(BaseModel):
    """Rule version and scope configuration."""

    version: str
    scope_file: str = "RULE_SCOPE.md"


class SeedSpec(BaseModel):
    """Seed generation configuration."""

    start: int = 0
    count: int = 1
    explicit: list[int] | None = None
    common_walls: bool = True


class MatchSpec(BaseModel):
    """Match configuration."""

    preset: Literal["tonpuu", "hanchan", "custom"] = "hanchan"
    max_hands: int | None = None
    allow_negative: bool = False
    step_limit: int = 20000


class RuntimeSpec(BaseModel):
    """Runtime configuration."""

    mode: Literal["serial"] = "serial"
    debug_snapshots: bool = False
    no_persist: bool = True
    resume: bool = True
    fail_fast: bool = False


class ArtifactSpec(BaseModel):
    """Artifact output configuration."""

    output_root: str = "runs"
    save_replay: bool = True
    save_events: bool = True
    save_decisions: bool = True
    save_prompts: bool = False
    save_debug_snapshots: bool = False
    sqlite_index: bool = True


class ExperimentSpec(BaseModel):
    """Top-level experiment configuration."""

    experiment: ExperimentMetaSpec
    rules: RuleSpec
    seeds: SeedSpec
    match: MatchSpec
    runtime: RuntimeSpec = Field(default_factory=RuntimeSpec)
    artifacts: ArtifactSpec = Field(default_factory=ArtifactSpec)
    policies: dict[str, PolicySpec]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentSpec":
        """Load experiment spec from YAML file.

        Args:
            path: Path to YAML configuration file.

        Returns:
            ExperimentSpec instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            pydantic.ValidationError: If the configuration is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.model_validate(data)
