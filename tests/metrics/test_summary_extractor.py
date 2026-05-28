"""Test SummaryExtractor."""

from metrics.extractors.summary import SummaryExtractor
from metrics.loader import JobSummary, RunData
from metrics.schema import MetricRecord


def test_summary_extractor_yields_match_end():
    """SummaryExtractor yields match_end record from summary."""
    summary = JobSummary(
        match_id="test-match",
        job_id="job-001",
        seed=42,
        outcome="completed",
        step_count=5040,
        hand_count=12,
        final_points=(30000, 25000, 20000, 15000),
        point_delta=(5000, 0, -5000, -10000),
        starting_points=(25000, 25000, 25000, 25000),
        duration_ms=12345.6,
        stopped_reason=None,
    )

    data = RunData(
        match_id="test-match",
        job_id="job-001",
        seed=42,
        decisions=[],
        events=[],
        summary=summary,
    )

    extractor = SummaryExtractor()
    records = list(extractor.extract(data))

    assert len(records) == 1
    record = records[0]
    assert record.kind == "match_end"
    assert record.match_id == "test-match"
    assert record.job_id == "job-001"
    assert record.values["seed"] == 42
    assert record.values["outcome"] == "completed"
    assert record.values["step_count"] == 5040
    assert record.values["hand_count"] == 12
    assert record.values["duration_ms"] == 12345.6
    assert record.values["final_points"] == (30000, 25000, 20000, 15000)


def test_summary_extractor_no_summary():
    """SummaryExtractor yields nothing when summary is None."""
    data = RunData(
        match_id="test-match",
        job_id="job-001",
        seed=42,
        decisions=[],
        events=[],
        summary=None,
    )

    extractor = SummaryExtractor()
    records = list(extractor.extract(data))

    assert len(records) == 0


def test_summary_extractor_name():
    """SummaryExtractor has correct name."""
    extractor = SummaryExtractor()
    assert extractor.name == "summary"