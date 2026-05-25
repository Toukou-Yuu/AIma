"""Report generator: write metrics to various formats."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from metrics.schema import DecisionMetrics, MatchMetrics, PlayerMetrics


class ReportGenerator:
    """Generate reports from pipeline results.

    Supports CSV, JSON, and Markdown output formats.
    """

    def __init__(self, results: dict[str, Any]) -> None:
        """Initialize generator with pipeline results.

        Args:
            results: Dict from MetricsPipeline.run() output.
        """
        self.results = results

    def write_all(self, output_dir: Path) -> None:
        """Write all reports to output directory.

        Args:
            output_dir: Directory to write reports to.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        self.write_csv(output_dir)
        self.write_json(output_dir)
        self.write_markdown(output_dir)

    def write_csv(self, output_dir: Path) -> None:
        """Write CSV files for each metric type.

        Creates:
            - match_metrics.csv: one row per match
            - decision_metrics.csv: one row per (match_id, seat)
            - player_metrics.csv: one row per seat

        Args:
            output_dir: Directory to write CSV files to.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Match metrics
        match_metrics = self.results.get("match", [])
        if match_metrics and isinstance(match_metrics, list) and match_metrics:
            if isinstance(match_metrics[0], MatchMetrics):
                self._write_match_csv(output_dir / "match_metrics.csv", match_metrics)

        # Decision metrics
        decision_metrics = self.results.get("decision", [])
        if decision_metrics and isinstance(decision_metrics, list):
            if decision_metrics and isinstance(decision_metrics[0], DecisionMetrics):
                self._write_decision_csv(
                    output_dir / "decision_metrics.csv", decision_metrics
                )

        # Player metrics
        player_metrics = self.results.get("player", [])
        if player_metrics and isinstance(player_metrics, list):
            if player_metrics and isinstance(player_metrics[0], PlayerMetrics):
                self._write_player_csv(output_dir / "player_metrics.csv", player_metrics)

    def write_json(self, output_dir: Path) -> None:
        """Write JSON summary file.

        Creates:
            - reliability_summary.json: aggregated reliability metrics

        Args:
            output_dir: Directory to write JSON files to.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        summary = self._build_reliability_summary()
        with (output_dir / "reliability_summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def write_markdown(self, output_dir: Path) -> None:
        """Write Markdown report.

        Creates:
            - report.md: summary tables and analysis

        Args:
            output_dir: Directory to write Markdown file to.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        lines.append("# Metrics Report\n")

        # Match summary
        match_metrics = self.results.get("match", [])
        if match_metrics and isinstance(match_metrics, list) and match_metrics:
            if isinstance(match_metrics[0], MatchMetrics):
                lines.append(self._format_match_section(match_metrics))

        # Player summary
        player_metrics = self.results.get("player", [])
        if player_metrics and isinstance(player_metrics, list) and player_metrics:
            if isinstance(player_metrics[0], PlayerMetrics):
                lines.append(self._format_player_section(player_metrics))

        # Reliability summary
        lines.append(self._format_reliability_section())

        with (output_dir / "report.md").open("w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _write_match_csv(self, path: Path, metrics: list[MatchMetrics]) -> None:
        """Write match metrics to CSV."""
        fieldnames = [
            "match_id",
            "job_id",
            "seed",
            "outcome",
            "step_count",
            "hand_count",
            "total_duration_ms",
            "final_points_0",
            "final_points_1",
            "final_points_2",
            "final_points_3",
            "point_delta_0",
            "point_delta_1",
            "point_delta_2",
            "point_delta_3",
            "ron_count_0",
            "ron_count_1",
            "ron_count_2",
            "ron_count_3",
            "tsumo_count_0",
            "tsumo_count_1",
            "tsumo_count_2",
            "tsumo_count_3",
            "riichi_count_0",
            "riichi_count_1",
            "riichi_count_2",
            "riichi_count_3",
            "total_prompt_tokens",
            "total_completion_tokens",
            "avg_prompt_tokens_per_decision",
            "avg_completion_tokens_per_decision",
            "peak_prompt_tokens",
            "memory_injected_tokens_total",
            "decision_count",
            "parse_success_count",
            "parse_fallback_count",
            "parse_error_count",
            "avg_latency_ms",
            "p99_latency_ms",
        ]

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in metrics:
                row = {
                    "match_id": m.match_id,
                    "job_id": m.job_id,
                    "seed": m.seed,
                    "outcome": m.outcome,
                    "step_count": m.step_count,
                    "hand_count": m.hand_count,
                    "total_duration_ms": m.total_duration_ms,
                    "final_points_0": m.final_points[0],
                    "final_points_1": m.final_points[1],
                    "final_points_2": m.final_points[2],
                    "final_points_3": m.final_points[3],
                    "point_delta_0": m.point_delta[0],
                    "point_delta_1": m.point_delta[1],
                    "point_delta_2": m.point_delta[2],
                    "point_delta_3": m.point_delta[3],
                    "ron_count_0": m.ron_count[0],
                    "ron_count_1": m.ron_count[1],
                    "ron_count_2": m.ron_count[2],
                    "ron_count_3": m.ron_count[3],
                    "tsumo_count_0": m.tsumo_count[0],
                    "tsumo_count_1": m.tsumo_count[1],
                    "tsumo_count_2": m.tsumo_count[2],
                    "tsumo_count_3": m.tsumo_count[3],
                    "riichi_count_0": m.riichi_count[0],
                    "riichi_count_1": m.riichi_count[1],
                    "riichi_count_2": m.riichi_count[2],
                    "riichi_count_3": m.riichi_count[3],
                    "total_prompt_tokens": m.total_prompt_tokens,
                    "total_completion_tokens": m.total_completion_tokens,
                    "avg_prompt_tokens_per_decision": m.avg_prompt_tokens_per_decision,
                    "avg_completion_tokens_per_decision": m.avg_completion_tokens_per_decision,
                    "peak_prompt_tokens": m.peak_prompt_tokens,
                    "memory_injected_tokens_total": m.memory_injected_tokens_total,
                    "decision_count": m.decision_count,
                    "parse_success_count": m.parse_success_count,
                    "parse_fallback_count": m.parse_fallback_count,
                    "parse_error_count": m.parse_error_count,
                    "avg_latency_ms": m.avg_latency_ms,
                    "p99_latency_ms": m.p99_latency_ms,
                }
                writer.writerow(row)

    def _write_decision_csv(
        self, path: Path, metrics: list[DecisionMetrics]
    ) -> None:
        """Write decision metrics to CSV."""
        fieldnames = [
            "match_id",
            "job_id",
            "seat",
            "hand_index",
            "step_index",
            "parse_status",
            "fallback_used",
            "latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "memory_injected_tokens",
            "action_kind",
        ]

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in metrics:
                row = {
                    "match_id": m.match_id,
                    "job_id": m.job_id,
                    "seat": m.seat,
                    "hand_index": m.hand_index,
                    "step_index": m.step_index,
                    "parse_status": m.parse_status,
                    "fallback_used": m.fallback_used,
                    "latency_ms": m.latency_ms if m.latency_ms is not None else "",
                    "prompt_tokens": m.prompt_tokens if m.prompt_tokens is not None else "",
                    "completion_tokens": (
                        m.completion_tokens if m.completion_tokens is not None else ""
                    ),
                    "memory_injected_tokens": (
                        m.memory_injected_tokens if m.memory_injected_tokens is not None else ""
                    ),
                    "action_kind": m.action_kind,
                }
                writer.writerow(row)

    def _write_player_csv(self, path: Path, metrics: list[PlayerMetrics]) -> None:
        """Write player metrics to CSV."""
        fieldnames = [
            "seat",
            "match_count",
            "avg_final_points",
            "avg_point_delta",
            "total_point_delta",
            "total_ron_count",
            "total_tsumo_count",
            "total_riichi_count",
            "riichi_success_rate",
            "avg_prompt_tokens",
            "avg_completion_tokens",
            "total_tokens",
            "avg_memory_injected_tokens",
            "total_decisions",
            "parse_success_rate",
            "avg_latency_ms",
            "p99_latency_ms",
        ]

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in metrics:
                row = {
                    "seat": m.seat,
                    "match_count": m.match_count,
                    "avg_final_points": m.avg_final_points,
                    "avg_point_delta": m.avg_point_delta,
                    "total_point_delta": m.total_point_delta,
                    "total_ron_count": m.total_ron_count,
                    "total_tsumo_count": m.total_tsumo_count,
                    "total_riichi_count": m.total_riichi_count,
                    "riichi_success_rate": m.riichi_success_rate,
                    "avg_prompt_tokens": m.avg_prompt_tokens,
                    "avg_completion_tokens": m.avg_completion_tokens,
                    "total_tokens": m.total_tokens,
                    "avg_memory_injected_tokens": m.avg_memory_injected_tokens,
                    "total_decisions": m.total_decisions,
                    "parse_success_rate": m.parse_success_rate,
                    "avg_latency_ms": m.avg_latency_ms,
                    "p99_latency_ms": m.p99_latency_ms,
                }
                writer.writerow(row)

    def _build_reliability_summary(self) -> dict[str, Any]:
        """Build reliability summary from all metrics."""
        match_metrics = self.results.get("match", [])
        decision_metrics = self.results.get("decision", [])

        total_decisions = 0
        parse_success_count = 0
        parse_fallback_count = 0
        parse_error_count = 0
        latencies: list[float] = []
        prompt_tokens_list: list[int] = []
        completion_tokens_list: list[int] = []
        memory_injected_list: list[int] = []

        # Aggregate from decision metrics
        if isinstance(decision_metrics, list):
            for d in decision_metrics:
                if isinstance(d, DecisionMetrics):
                    total_decisions += 1
                    if d.parse_status == "ok":
                        parse_success_count += 1
                    elif d.parse_status == "fallback":
                        parse_fallback_count += 1
                    else:
                        parse_error_count += 1

                    if d.latency_ms is not None:
                        latencies.append(d.latency_ms)
                    if d.prompt_tokens is not None:
                        prompt_tokens_list.append(d.prompt_tokens)
                    if d.completion_tokens is not None:
                        completion_tokens_list.append(d.completion_tokens)
                    if d.memory_injected_tokens is not None:
                        memory_injected_list.append(d.memory_injected_tokens)

        # Calculate percentiles
        p50_latency = self._percentile(latencies, 50) if latencies else 0.0
        p95_latency = self._percentile(latencies, 95) if latencies else 0.0
        p99_latency = self._percentile(latencies, 99) if latencies else 0.0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        avg_prompt = (
            sum(prompt_tokens_list) / len(prompt_tokens_list)
            if prompt_tokens_list
            else 0.0
        )
        avg_completion = (
            sum(completion_tokens_list) / len(completion_tokens_list)
            if completion_tokens_list
            else 0.0
        )
        avg_memory = (
            sum(memory_injected_list) / len(memory_injected_list)
            if memory_injected_list
            else 0.0
        )

        # Count matches with over-budget (placeholder: matches with > 5000 avg prompt tokens)
        matches_with_over_budget = 0
        if isinstance(match_metrics, list):
            for m in match_metrics:
                if isinstance(m, MatchMetrics) and m.avg_prompt_tokens_per_decision > 5000:
                    matches_with_over_budget += 1

        total_matches = len(match_metrics) if isinstance(match_metrics, list) else 0
        over_budget_rate = matches_with_over_budget / total_matches if total_matches > 0 else 0.0

        return {
            "total_decisions": total_decisions,
            "parse_success_count": parse_success_count,
            "parse_fallback_count": parse_fallback_count,
            "parse_error_count": parse_error_count,
            "parse_success_rate": (
                parse_success_count / total_decisions if total_decisions > 0 else 1.0
            ),
            "parse_fallback_rate": (
                parse_fallback_count / total_decisions if total_decisions > 0 else 0.0
            ),
            "parse_error_rate": (
                parse_error_count / total_decisions if total_decisions > 0 else 0.0
            ),
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "avg_prompt_tokens": avg_prompt,
            "avg_completion_tokens": avg_completion,
            "avg_memory_injected_tokens": avg_memory,
            "matches_with_over_budget": matches_with_over_budget,
            "over_budget_rate": over_budget_rate,
        }

    def _format_match_section(self, metrics: list[MatchMetrics]) -> str:
        """Format match metrics as Markdown section."""
        lines: list[str] = []
        lines.append("## Match Summary\n")
        lines.append("| Match ID | Outcome | Hands | Steps | Duration (ms) |")
        lines.append("|----------|----------|-------|-------|---------------|")

        for m in metrics[:10]:  # Limit to first 10 for readability
            lines.append(
                f"| {m.match_id[:8]}... | {m.outcome} | {m.hand_count} | {m.step_count} | {m.total_duration_ms:.0f} |"
            )

        if len(metrics) > 10:
            lines.append(f"\n... and {len(metrics) - 10} more matches")

        return "\n".join(lines) + "\n"

    def _format_player_section(self, metrics: list[PlayerMetrics]) -> str:
        """Format player metrics as Markdown section."""
        lines: list[str] = []
        lines.append("## Player Summary\n")
        lines.append(
            "| Seat | Matches | Avg Points | Avg Delta | Ron | Tsumo | Riichi |"
        )
        lines.append(
            "|------|---------|------------|-----------|-----|-------|--------|"
        )

        for p in metrics:
            lines.append(
                f"| {p.seat} | {p.match_count} | {p.avg_final_points:.0f} | "
                f"{p.avg_point_delta:+.0f} | {p.total_ron_count} | "
                f"{p.total_tsumo_count} | {p.total_riichi_count} |"
            )

        return "\n".join(lines) + "\n"

    def _format_reliability_section(self) -> str:
        """Format reliability summary as Markdown section."""
        summary = self._build_reliability_summary()
        lines: list[str] = []
        lines.append("## Reliability Summary\n")
        lines.append(f"- **Total Decisions**: {summary['total_decisions']}")
        lines.append(
            f"- **Parse Success Rate**: {summary['parse_success_rate']:.1%}"
        )
        lines.append(
            f"- **Parse Fallback Rate**: {summary['parse_fallback_rate']:.1%}"
        )
        lines.append(
            f"- **Parse Error Rate**: {summary['parse_error_rate']:.1%}"
        )
        lines.append(f"- **Avg Latency**: {summary['avg_latency_ms']:.1f} ms")
        lines.append(f"- **P99 Latency**: {summary['p99_latency_ms']:.1f} ms")
        lines.append(f"- **Avg Prompt Tokens**: {summary['avg_prompt_tokens']:.0f}")
        lines.append(
            f"- **Avg Completion Tokens**: {summary['avg_completion_tokens']:.0f}"
        )

        return "\n".join(lines) + "\n"

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