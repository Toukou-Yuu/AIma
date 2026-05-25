"""Decision-level reducer: extract DecisionMetrics from decision records."""

from __future__ import annotations

from metrics.schema import DecisionMetrics, MetricRecord


class DecisionReducer:
    """Extract DecisionMetrics from decision MetricRecords.

    Processes decision records to produce per-decision metrics.
    Each decision record becomes one DecisionMetrics.
    """

    @property
    def name(self) -> str:
        return "decision"

    def reduce(self, records: list[MetricRecord]) -> list[DecisionMetrics]:
        """Extract DecisionMetrics from decision records.

        Args:
            records: List of metric records.

        Returns:
            List of DecisionMetrics, one per decision record.
        """
        result: list[DecisionMetrics] = []

        for record in records:
            if record.kind != "decision":
                continue

            metrics = self._extract_decision(record)
            result.append(metrics)

        return result

    def _extract_decision(self, record: MetricRecord) -> DecisionMetrics:
        """Extract DecisionMetrics from a single decision record."""
        values = record.values

        # Parse status
        parse_status = values.get("parse_status", "ok")
        fallback_used = values.get("fallback_used", False)

        # Latency
        latency_ms = values.get("latency_ms")

        # Tokens
        prompt_tokens = values.get("prompt_tokens")
        completion_tokens = values.get("completion_tokens")
        memory_injected_tokens = values.get("memory_injected_tokens")

        # Action kind
        action_kind = values.get("action_kind", "unknown")

        return DecisionMetrics(
            match_id=record.match_id,
            job_id=record.job_id,
            seat=record.seat if record.seat is not None else 0,
            hand_index=record.hand_index if record.hand_index is not None else 0,
            step_index=values.get("step_index", 0),
            parse_status=parse_status,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            memory_injected_tokens=memory_injected_tokens,
            action_kind=action_kind,
        )