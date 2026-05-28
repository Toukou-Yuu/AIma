"""Match-level extractors: MatchEndExtractor, HandOverExtractor."""

from __future__ import annotations

from typing import Iterator

from metrics.extractors.base import BaseExtractor
from metrics.loader import RunData
from metrics.schema import MetricRecord


class MatchEndExtractor(BaseExtractor):
    """Extract match end metrics.

    Yields one MetricRecord with:
        - kind: "match_end"
        - values: ranking, final_scores
    """

    name = "match_end"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract match end metrics from events.

        Args:
            data: Run data containing events.

        Yields:
            MetricRecord for match end.
        """
        for event_record in data.events:
            event = event_record.event
            if event.get("event_type") != "match_end":
                continue

            ranking = event.get("ranking", (1, 1, 1, 1))
            final_scores = event.get("final_scores", (0, 0, 0, 0))

            # Ensure tuples
            if isinstance(ranking, list):
                ranking = tuple(ranking)
            if isinstance(final_scores, list):
                final_scores = tuple(final_scores)

            yield MetricRecord(
                kind="match_end",
                match_id=data.match_id,
                job_id=data.job_id,
                seat=None,
                hand_index=None,
                values={
                    "ranking": ranking,
                    "final_scores": final_scores,
                },
            )
            # Only one match end per match
            break


class HandOverExtractor(BaseExtractor):
    """Extract hand over metrics.

    Yields one MetricRecord with:
        - kind: "hand_over"
        - values: hand_count, winners, payments
    """

    name = "hand_over"

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract hand over metrics from events.

        Args:
            data: Run data containing events.

        Yields:
            MetricRecord for each hand over event.
        """
        hand_index = 0
        for event_record in data.events:
            event = event_record.event
            if event.get("event_type") == "hand_over":
                winners = event.get("winners", [])
                payments = event.get("payments", (0, 0, 0, 0))

                if isinstance(winners, list):
                    winners = tuple(winners)
                if isinstance(payments, list):
                    payments = tuple(payments)

                yield MetricRecord(
                    kind="hand_over",
                    match_id=data.match_id,
                    job_id=data.job_id,
                    seat=None,
                    hand_index=hand_index,
                    values={
                        "winners": winners,
                        "payments": payments,
                        "step_index": event_record.step_index,
                    },
                )
                hand_index += 1