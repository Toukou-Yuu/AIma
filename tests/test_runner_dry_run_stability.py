"""H-35: Batch dry-run stability test - 100 seeds x max_hands=8"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.engine.phase import GamePhase
from llm.config import MatchEndCondition
from llm.runner import run_llm_match
from tests.llm_test_utils import load_test_runtime_config, load_test_seat_llm_configs

pytestmark = pytest.mark.slow

NUM_SEEDS = 10  # Reduced for CI; full run: 100
MAX_HANDS = 8
MAX_KERNEL_STEPS = 6000  # Safety limit (typical: ~500-700 steps/hand, max_hands=8 → ~6000)
SUCCESS_REASONS = ("match_end", "hands_completed:8")


@pytest.mark.parametrize("seed", range(NUM_SEEDS))
def test_dry_run_stability_single_seed(seed: int) -> None:
    """Each seed must complete max_hands=8 without crash."""
    match_end = MatchEndCondition(type="hands", value=MAX_HANDS, allow_negative=False)
    runtime = load_test_runtime_config()

    result = run_llm_match(
        seed=seed,
        match_end=match_end,
        dry_run=True,
        request_delay_seconds=0.0,
        history_budget=runtime.history_budget,
        context_scope=runtime.context_scope,
        compression_level=runtime.compression_level,
        context_compression_threshold=runtime.context_compression_threshold,
        seat_llm_configs=load_test_seat_llm_configs(),
        prompt_format=runtime.prompt_format,
        enable_conversation_logging=False,
    )

    assert result.kernel_steps < MAX_KERNEL_STEPS, f"seed={seed} exceeded step limit"
    assert result.stopped_reason.startswith(SUCCESS_REASONS[0]) or result.stopped_reason.startswith(
        SUCCESS_REASONS[1]
    ), f"seed={seed} unexpected stop: {result.stopped_reason}"
    assert result.final_state.phase == GamePhase.MATCH_END, f"seed={seed} wrong phase: {result.final_state.phase.value}"


def test_dry_run_batch_summary(tmp_path: Path) -> None:
    """Batch summary with failure replay export."""
    failures: list[dict] = []
    match_end = MatchEndCondition(type="hands", value=MAX_HANDS, allow_negative=False)
    runtime = load_test_runtime_config()
    seat_configs = load_test_seat_llm_configs()

    for seed in range(NUM_SEEDS):
        result = run_llm_match(
            seed=seed,
            match_end=match_end,
            dry_run=True,
            request_delay_seconds=0.0,
            history_budget=runtime.history_budget,
            context_scope=runtime.context_scope,
            compression_level=runtime.compression_level,
            context_compression_threshold=runtime.context_compression_threshold,
            seat_llm_configs=seat_configs,
            prompt_format=runtime.prompt_format,
            enable_conversation_logging=False,
        )

        if not (
            result.stopped_reason.startswith(SUCCESS_REASONS[0])
            or result.stopped_reason.startswith(SUCCESS_REASONS[1])
        ):
            failures.append(
                {
                    "seed": seed,
                    "stopped_reason": result.stopped_reason,
                    "kernel_steps": result.kernel_steps,
                    "phase": result.final_state.phase.value,
                }
            )

    if failures:
        replay_file = tmp_path / "stability_failures.json"
        replay_file.write_text(json.dumps(failures, indent=2))

    assert len(failures) == 0, f"{len(failures)} seeds failed: {[f['seed'] for f in failures]}"