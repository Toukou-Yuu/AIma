"""Summary extractor: extract match_end from RunData.summary."""

from __future__ import annotations

from typing import Iterator

from metrics.extractors.base import BaseExtractor
from metrics.loader import RunData
from metrics.schema import MetricRecord


class SummaryExtractor(BaseExtractor):
    """Extract match end metrics from RunData.summary.

    Yields one MetricRecord with:
        - kind: "match_end"
        - values: seed, outcome, step_count, hand_count, duration_ms,
                  final_points, point_delta, starting_points
    """

    name = "summary"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract match end metrics from summary.

        Args:
            data: Run data containing summary.

        Yields:
            MetricRecord for match end from summary.
        """
        summary = data.summary
        if summary is None:
            return

        yield MetricRecord(
            kind="match_end",
            match_id=data.match_id,
            job_id=data.job_id,
            seat=None,
            hand_index=None,
            values={
                "seed": summary.seed,
                "outcome": summary.outcome,
                "step_count": summary.step_count,
                "hand_count": summary.hand_count,
                "duration_ms": summary.duration_ms,
                "final_points": summary.final_points,
                "point_delta": summary.point_delta,
                "starting_points": summary.starting_points,
            },
        )