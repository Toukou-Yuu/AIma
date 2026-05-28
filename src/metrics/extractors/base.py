"""Base extractor protocol for metrics extraction."""

from __future__ import annotations

from typing import Iterator, Protocol

from metrics.loader import RunData
from metrics.schema import MetricRecord


class BaseExtractor(Protocol):
    """Protocol for metric extractors.

    Extractors take RunData and yield MetricRecords.
    Each extractor focuses on a specific metric kind.
    """

    name: str

    def extract(self, data: RunData) -> Iterator[MetricRecord]:
        """Extract metric records from run data.

        Args:
            data: Run data containing decisions, events, and summary.

        Yields:
            MetricRecord instances.
        """
        ...