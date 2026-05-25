"""Match-level reducer: aggregate to MatchMetrics."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from metrics.schema import MatchMetrics, MetricRecord


# Heuristic: completion tokens ~ 10% of prompt tokens
COMPLETION_TOKEN_RATIO = 0.1


class MatchReducer:
    """Aggregate MetricRecords into MatchMetrics per match.

    Processes:
    - match_end: match outcome and final scores
    - hand_over: hand count
    - ron, tsumo, riichi: win/riichi statistics per seat
    - decision: token usage and latency
    """

    @property
    def name(self) -> str:
        return "match"

    def reduce(self, records: list[MetricRecord]) -> list[MatchMetrics]:
        """Aggregate records into MatchMetrics per match.

        Args:
            records: List of metric records.

        Returns:
            List of MatchMetrics, one per match.
        """
        # Group by match_id
        matches: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "match_id": "",
            "job_id": "",
            "seed": 0,
            "outcome": "completed",
            "step_count": 0,
            "hand_count": 0,
            "duration_ms": 0.0,
            "final_points": (25000, 25000, 25000, 25000),
            "point_delta": (0, 0, 0, 0),
            "starting_points": (25000, 25000, 25000, 25000),
            "ron_count": [0, 0, 0, 0],
            "tsumo_count": [0, 0, 0, 0],
            "riichi_count": [0, 0, 0, 0],
            "riichi_success_count": [0, 0, 0, 0],
            "decision_latencies": [],
            "prompt_tokens": [],
            "completion_tokens": [],
            "memory_injected_tokens": [],
            "peak_prompt_tokens": 0,
            "parse_status_counts": {"ok": 0, "fallback": 0, "error": 0},
        })

        for record in records:
            match_id = record.match_id
            matches[match_id]["match_id"] = match_id
            matches[match_id]["job_id"] = record.job_id

            if record.kind == "match_end":
                self._process_match_end(matches[match_id], record)
            elif record.kind == "hand_over":
                matches[match_id]["hand_count"] += 1
            elif record.kind == "ron":
                self._process_ron(matches[match_id], record)
            elif record.kind == "tsumo":
                self._process_tsumo(matches[match_id], record)
            elif record.kind == "riichi":
                self._process_riichi(matches[match_id], record)
            elif record.kind == "decision":
                self._process_decision(matches[match_id], record)

        # Build MatchMetrics for each match
        result: list[MatchMetrics] = []
        for match_id, data in matches.items():
            if not match_id:
                continue

            metrics = self._build_metrics(data)
            result.append(metrics)

        return result

    def _process_match_end(self, data: dict[str, Any], record: MetricRecord) -> None:
        """Process match_end record."""
        values = record.values
        if "seed" in values:
            data["seed"] = values["seed"]
        if "outcome" in values:
            data["outcome"] = values["outcome"]
        if "step_count" in values:
            data["step_count"] = values["step_count"]
        if "duration_ms" in values:
            data["duration_ms"] = values["duration_ms"]
        if "final_points" in values:
            points = values["final_points"]
            data["final_points"] = tuple(points) if len(points) == 4 else data["final_points"]
        if "point_delta" in values:
            delta = values["point_delta"]
            data["point_delta"] = tuple(delta) if len(delta) == 4 else data["point_delta"]
        if "starting_points" in values:
            start = values["starting_points"]
            data["starting_points"] = tuple(start) if len(start) == 4 else data["starting_points"]

    def _process_ron(self, data: dict[str, Any], record: MetricRecord) -> None:
        """Process ron record: winner gets +1 to ron_count."""
        values = record.values
        winner_seat = values.get("winner_seat", record.seat)
        if winner_seat is not None and 0 <= winner_seat < 4:
            data["ron_count"][winner_seat] += 1

    def _process_tsumo(self, data: dict[str, Any], record: MetricRecord) -> None:
        """Process tsumo record: winner gets +1 to tsumo_count."""
        values = record.values
        winner_seat = values.get("winner_seat", record.seat)
        if winner_seat is not None and 0 <= winner_seat < 4:
            data["tsumo_count"][winner_seat] += 1

    def _process_riichi(self, data: dict[str, Any], record: MetricRecord) -> None:
        """Process riichi record: seat gets +1 to riichi_count.

        If success=True, also +1 to riichi_success_count.
        """
        seat = record.seat
        if seat is None or not (0 <= seat < 4):
            return

        data["riichi_count"][seat] += 1
        if record.values.get("success"):
            data["riichi_success_count"][seat] += 1

    def _process_decision(self, data: dict[str, Any], record: MetricRecord) -> None:
        """Process decision record for token/latency statistics."""
        values = record.values

        # Latency
        latency = values.get("latency_ms")
        if latency is not None:
            data["decision_latencies"].append(latency)

        # Tokens
        prompt_tokens = values.get("prompt_tokens")
        if prompt_tokens is not None:
            data["prompt_tokens"].append(prompt_tokens)
            # Use heuristic for completion tokens if not available
            completion = values.get("completion_tokens")
            if completion is None:
                completion = int(prompt_tokens * COMPLETION_TOKEN_RATIO)
            data["completion_tokens"].append(completion)
            if prompt_tokens > data["peak_prompt_tokens"]:
                data["peak_prompt_tokens"] = prompt_tokens

        memory_injected = values.get("memory_injected_tokens")
        if memory_injected is not None:
            data["memory_injected_tokens"].append(memory_injected)

        # Parse status
        parse_status = values.get("parse_status", "ok")
        if parse_status in data["parse_status_counts"]:
            data["parse_status_counts"][parse_status] += 1

    def _build_metrics(self, data: dict[str, Any]) -> MatchMetrics:
        """Build MatchMetrics from aggregated data."""
        latencies = data["decision_latencies"]
        prompt_tokens = data["prompt_tokens"]
        completion_tokens = data["completion_tokens"]
        memory_tokens = data["memory_injected_tokens"]

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        p99_latency = self._percentile(latencies, 99) if latencies else 0.0

        total_prompt = sum(prompt_tokens)
        total_completion = sum(completion_tokens)
        avg_prompt = total_prompt / len(prompt_tokens) if prompt_tokens else 0.0
        avg_completion = total_completion / len(completion_tokens) if completion_tokens else 0.0

        return MatchMetrics(
            match_id=data["match_id"],
            job_id=data["job_id"],
            seed=data["seed"],
            outcome=data["outcome"],
            step_count=data["step_count"],
            hand_count=data["hand_count"],
            total_duration_ms=data["duration_ms"],
            final_points=data["final_points"],
            point_delta=data["point_delta"],
            starting_points=data["starting_points"],
            ron_count=tuple(data["ron_count"]),
            tsumo_count=tuple(data["tsumo_count"]),
            riichi_count=tuple(data["riichi_count"]),
            riichi_success_count=tuple(data["riichi_success_count"]),
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            avg_prompt_tokens_per_decision=avg_prompt,
            avg_completion_tokens_per_decision=avg_completion,
            peak_prompt_tokens=data["peak_prompt_tokens"],
            memory_injected_tokens_total=sum(memory_tokens),
            decision_count=len(latencies),
            parse_success_count=data["parse_status_counts"]["ok"],
            parse_fallback_count=data["parse_status_counts"]["fallback"],
            parse_error_count=data["parse_status_counts"]["error"],
            avg_latency_ms=avg_latency,
            p99_latency_ms=p99_latency,
        )

    @staticmethod
    def _percentile(values: list[float], p: int) -> float:
        """Calculate percentile of a list.

        Args:
            values: List of values (will be sorted in place).
            p: Percentile (0-100).

        Returns:
            The percentile value.
        """
        if not values:
            return 0.0
        sorted_values = sorted(values)
        n = len(sorted_values)
        idx = int(n * p / 100)
        idx = min(idx, n - 1)
        return sorted_values[idx]