"""Metrics pipeline: orchestrate extractors and reducers."""

from __future__ import annotations

from typing import Any

from metrics.extractors import (
    CallExtractor,
    DecisionExtractor,
    FlowExtractor,
    HandOverExtractor,
    MatchEndExtractor,
    RiichiExtractor,
    RonExtractor,
    TsumoExtractor,
)
from metrics.extractors.base import BaseExtractor
from metrics.loader import RunData
from metrics.reducers import DecisionReducer, MatchReducer, PlayerReducer
from metrics.reducers.base import BaseReducer


class MetricsPipeline:
    """Orchestrate extractors and reducers to produce metrics.

    The pipeline:
    1. Runs all extractors on each RunData to produce MetricRecords
    2. Runs all reducers on the aggregated records to produce metrics
    """

    def __init__(
        self,
        extractors: list[BaseExtractor],
        reducers: list[BaseReducer],
    ) -> None:
        """Initialize pipeline with extractors and reducers.

        Args:
            extractors: List of extractors to run.
            reducers: List of reducers to run.
        """
        self.extractors = extractors
        self.reducers = reducers

    def run(self, run_data: list[RunData]) -> dict[str, Any]:
        """Run the pipeline on the provided data.

        Args:
            run_data: List of RunData from loaded jobs.

        Returns:
            Dict mapping reducer names to their output metrics.
        """
        # 1. Extract all records from all extractors
        records = []
        for data in run_data:
            for extractor in self.extractors:
                records.extend(extractor.extract(data))

        # 2. Reduce records by each reducer
        results: dict[str, Any] = {}
        for reducer in self.reducers:
            results[reducer.name] = reducer.reduce(records)

        return results


def create_default_pipeline() -> MetricsPipeline:
    """Create a pipeline with all default extractors and reducers.

    Returns:
        MetricsPipeline configured with all standard extractors and reducers.
    """
    return MetricsPipeline(
        extractors=[
            MatchEndExtractor(),
            HandOverExtractor(),
            DecisionExtractor(),
            RonExtractor(),
            TsumoExtractor(),
            RiichiExtractor(),
            CallExtractor(),
            FlowExtractor(),
        ],
        reducers=[
            MatchReducer(),
            DecisionReducer(),
            PlayerReducer(),
        ],
    )