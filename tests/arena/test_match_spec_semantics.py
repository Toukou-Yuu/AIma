"""MatchSpec preset/max_hands/step_limit semantics."""

from __future__ import annotations

import pytest

from arena import GameEngine, MatchRunner
from experiments.schema import MatchSpec
from policies import FirstLegalPolicy


def _runner() -> MatchRunner:
    policies = {seat: FirstLegalPolicy(f"seat_{seat}") for seat in range(4)}
    return MatchRunner(GameEngine(), policies)


@pytest.mark.parametrize(
    ("preset", "max_hands", "expected_hands"),
    [
        ("tonpuu", None, 4),
        ("hanchan", None, 8),
    ],
)
def test_natural_preset_completion(
    preset: str,
    max_hands: int | None,
    expected_hands: int,
) -> None:
    result = _runner().run(MatchSpec(preset=preset, max_hands=max_hands), seed=42)

    assert result.outcome == "completed"
    assert result.stopped_reason is None
    assert result.final_phase == "match_end"
    assert result.hand_count == expected_hands


@pytest.mark.parametrize(
    ("preset", "max_hands"),
    [
        ("tonpuu", 1),
        ("hanchan", 2),
    ],
)
def test_max_hands_truncates_after_completed_hands(preset: str, max_hands: int) -> None:
    result = _runner().run(MatchSpec(preset=preset, max_hands=max_hands), seed=42)

    assert result.outcome == "truncated"
    assert result.stopped_reason == "max_hands_reached"
    assert result.hand_count == max_hands
    assert result.final_phase == "in_round"


def test_step_limit_has_distinct_outcome() -> None:
    policies = {seat: FirstLegalPolicy(f"seat_{seat}") for seat in range(4)}
    result = MatchRunner(GameEngine(), policies, step_limit=20).run(
        MatchSpec(preset="tonpuu", max_hands=None),
        seed=42,
    )

    assert result.outcome == "step_limit_reached"
    assert result.stopped_reason == "step_limit_exceeded"
