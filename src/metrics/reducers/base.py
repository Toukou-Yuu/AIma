"""Base reducer protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from metrics.schema import MetricRecord


@runtime_checkable
class BaseReducer(Protocol):
    """Protocol for metric reducers.

    Reducers aggregate MetricRecords into structured metrics.
    Each reducer handles specific kinds of records and produces
    a specific type of aggregated metrics.
    """

    @property
    def name(self) -> str:
        """Reducer name for identification."""
        ...

    def reduce(self, records: list[MetricRecord]) -> Any:
        """Aggregate records into metrics.

        Args:
            records: List of metric records to aggregate.

        Returns:
            Aggregated metrics (structure depends on reducer).
        """
        ...