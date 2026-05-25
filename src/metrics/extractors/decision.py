"""Decision extractor: extract metrics from decision records."""

from __future__ import annotations

from typing import Iterator

from metrics.extractors.base import BaseExtractor
from metrics.loader import RunData
from metrics.schema import MetricRecord


class DecisionExtractor(BaseExtractor):
    """Extract decision metrics from decisions.jsonl.

    Yields MetricRecord for each decision with:
        - kind: "decision"
        - seat: player seat
        - hand_index: hand index (from step_index, estimated)
        - values: parse_status, fallback_used, latency_ms,
                  prompt_tokens, completion_tokens, memory_injected_tokens, action_kind
    """

    name = "decision"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract decision metrics from decision records.

        Args:
            data: Run data containing decisions.

        Yields:
            MetricRecord for each decision.
        """
        for decision in data.decisions:
            diagnostics = decision.diagnostics

            # Extract token info from diagnostics
            prompt_tokens = diagnostics.get("prompt_tokens")
            completion_tokens = diagnostics.get("completion_tokens")
            memory_injected_tokens = diagnostics.get("memory_injected_tokens")

            # Extract action kind
            action = decision.action
            action_kind = action.get("kind", "unknown")

            # Determine hand_index (approximate from step_index)
            # A typical hand has ~20-30 steps, but we don't have exact hand boundaries
            # We'll track hand_index from events if available, otherwise use step_index // 25
            hand_index = decision.step_index // 25  # rough estimate

            yield MetricRecord(
                kind="decision",
                match_id=data.match_id,
                job_id=data.job_id,
                seat=decision.seat,
                hand_index=hand_index,
                values={
                    "step_index": decision.step_index,
                    "parse_status": decision.parse_status,
                    "fallback_used": decision.fallback_used,
                    "latency_ms": decision.latency_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "memory_injected_tokens": memory_injected_tokens,
                    "action_kind": action_kind,
                },
            )