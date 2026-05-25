"""Player-level reducer: aggregate to PlayerMetrics across matches."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from metrics.schema import MetricRecord, PlayerMetrics


class PlayerReducer:
    """Aggregate MetricRecords into PlayerMetrics per seat.

    Cross-match aggregation for each seat (player).
    Processes match_end, ron, tsumo, riichi, decision records.
    """

    @property
    def name(self) -> str:
        return "player"

    def reduce(self, records: list[MetricRecord]) -> list[PlayerMetrics]:
        """Aggregate records into PlayerMetrics per seat.

        Args:
            records: List of metric records.

        Returns:
            List of PlayerMetrics, one per seat.
        """
        # Aggregate per seat
        seats: dict[int, dict[str, Any]] = defaultdict(lambda: {
            "match_ids": set(),
            "final_points": [],
            "point_deltas": [],
            "ron_count": 0,
            "tsumo_count": 0,
            "riichi_count": 0,
            "riichi_success_count": 0,
            "prompt_tokens": [],
            "completion_tokens": [],
            "memory_injected_tokens": [],
            "decision_latencies": [],
            "parse_status_counts": {"ok": 0, "fallback": 0, "error": 0},
        })

        for record in records:
            if record.kind == "match_end":
                self._process_match_end(seats, record)
            elif record.kind == "ron":
                self._process_ron(seats, record)
            elif record.kind == "tsumo":
                self._process_tsumo(seats, record)
            elif record.kind == "riichi":
                self._process_riichi(seats, record)
            elif record.kind == "decision":
                self._process_decision(seats, record)

        # Build PlayerMetrics for each seat
        result: list[PlayerMetrics] = []
        for seat, data in sorted(seats.items()):
            metrics = self._build_metrics(seat, data)
            result.append(metrics)

        return result

    def _process_match_end(
        self,
        seats: dict[int, dict[str, Any]],
        record: MetricRecord,
    ) -> None:
        """Process match_end to record final points per seat."""
        values = record.values
        final_points = values.get("final_points", (25000, 25000, 25000, 25000))
        point_delta = values.get("point_delta", (0, 0, 0, 0))
        match_id = record.match_id

        for seat in range(4):
            if seat < len(final_points):
                seats[seat]["final_points"].append(final_points[seat])
                seats[seat]["point_deltas"].append(point_delta[seat])
                seats[seat]["match_ids"].add(match_id)

    def _process_ron(self, seats: dict[int, dict[str, Any]], record: MetricRecord) -> None:
        """Process ron record: winner gets +1 to ron_count."""
        values = record.values
        winner_seat = values.get("winner_seat", record.seat)
        if winner_seat is not None and 0 <= winner_seat < 4:
            seats[winner_seat]["ron_count"] += 1

    def _process_tsumo(self, seats: dict[int, dict[str, Any]], record: MetricRecord) -> None:
        """Process tsumo record: winner gets +1 to tsumo_count."""
        values = record.values
        winner_seat = values.get("winner_seat", record.seat)
        if winner_seat is not None and 0 <= winner_seat < 4:
            seats[winner_seat]["tsumo_count"] += 1

    def _process_riichi(self, seats: dict[int, dict[str, Any]], record: MetricRecord) -> None:
        """Process riichi record: seat gets +1 to riichi_count."""
        seat = record.seat
        if seat is None or not (0 <= seat < 4):
            return

        seats[seat]["riichi_count"] += 1
        if record.values.get("success"):
            seats[seat]["riichi_success_count"] += 1

    def _process_decision(self, seats: dict[int, dict[str, Any]], record: MetricRecord) -> None:
        """Process decision record for token/latency statistics."""
        seat = record.seat
        if seat is None or not (0 <= seat < 4):
            return

        data = seats[seat]
        values = record.values

        # Latency
        latency = values.get("latency_ms")
        if latency is not None:
            data["decision_latencies"].append(latency)

        # Tokens
        prompt_tokens = values.get("prompt_tokens")
        if prompt_tokens is not None:
            data["prompt_tokens"].append(prompt_tokens)
            completion = values.get("completion_tokens")
            if completion is not None:
                data["completion_tokens"].append(completion)

        memory_injected = values.get("memory_injected_tokens")
        if memory_injected is not None:
            data["memory_injected_tokens"].append(memory_injected)

        # Parse status
        parse_status = values.get("parse_status", "ok")
        if parse_status in data["parse_status_counts"]:
            data["parse_status_counts"][parse_status] += 1

    def _build_metrics(self, seat: int, data: dict[str, Any]) -> PlayerMetrics:
        """Build PlayerMetrics from aggregated data."""
        match_count = len(data["match_ids"])
        final_points_list = data["final_points"]
        point_deltas = data["point_deltas"]
        prompt_tokens = data["prompt_tokens"]
        completion_tokens = data["completion_tokens"]
        memory_tokens = data["memory_injected_tokens"]
        latencies = data["decision_latencies"]

        # Points
        avg_final_points = (
            sum(final_points_list) / len(final_points_list)
            if final_points_list
            else 25000.0
        )
        avg_point_delta = (
            sum(point_deltas) / len(point_deltas)
            if point_deltas
            else 0.0
        )
        total_point_delta = sum(point_deltas)

        # Riichi success rate
        riichi_count = data["riichi_count"]
        riichi_success_rate = (
            data["riichi_success_count"] / riichi_count
            if riichi_count > 0
            else 0.0
        )

        # Tokens
        avg_prompt = sum(prompt_tokens) / len(prompt_tokens) if prompt_tokens else 0.0
        avg_completion = sum(completion_tokens) / len(completion_tokens) if completion_tokens else 0.0
        total_tokens = sum(prompt_tokens) + sum(completion_tokens)
        avg_memory = sum(memory_tokens) / len(memory_tokens) if memory_tokens else 0.0

        # Reliability
        total_decisions = len(latencies)
        parse_counts = data["parse_status_counts"]
        total_parse = parse_counts["ok"] + parse_counts["fallback"] + parse_counts["error"]
        parse_success_rate = parse_counts["ok"] / total_parse if total_parse > 0 else 1.0

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        p99_latency = self._percentile(latencies, 99) if latencies else 0.0

        return PlayerMetrics(
            seat=seat,
            match_count=match_count,
            avg_final_points=avg_final_points,
            avg_point_delta=avg_point_delta,
            total_point_delta=total_point_delta,
            total_ron_count=data["ron_count"],
            total_tsumo_count=data["tsumo_count"],
            total_riichi_count=riichi_count,
            riichi_success_rate=riichi_success_rate,
            avg_prompt_tokens=avg_prompt,
            avg_completion_tokens=avg_completion,
            total_tokens=total_tokens,
            avg_memory_injected_tokens=avg_memory,
            total_decisions=total_decisions,
            parse_success_rate=parse_success_rate,
            avg_latency_ms=avg_latency,
            p99_latency_ms=p99_latency,
        )

    @staticmethod
    def _percentile(values: list[float], p: int) -> float:
        """Calculate percentile of a list."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        n = len(sorted_values)
        idx = int(n * p / 100)
        idx = min(idx, n - 1)
        return sorted_values[idx]