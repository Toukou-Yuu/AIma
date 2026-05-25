"""测试 metrics/report.py。

测试 CSV/JSON/Markdown 输出。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from metrics.report import ReportGenerator
from metrics.schema import DecisionMetrics, MatchMetrics, PlayerMetrics


class TestReportGenerator:
    """ReportGenerator 测试。"""

    def test_write_all_creates_all_files(self) -> None:
        """write_all 创建所有文件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # 需要提供数据才能生成文件
            match_metrics = MatchMetrics(
                match_id="m1",
                job_id="j1",
                seed=42,
                outcome="completed",
                step_count=100,
                hand_count=4,
                total_duration_ms=1000.0,
                final_points=(25000, 25000, 25000, 25000),
                point_delta=(0, 0, 0, 0),
                starting_points=(25000, 25000, 25000, 25000),
                ron_count=(0, 0, 0, 0),
                tsumo_count=(0, 0, 0, 0),
                riichi_count=(0, 0, 0, 0),
                riichi_success_count=(0, 0, 0, 0),
                total_prompt_tokens=0,
                total_completion_tokens=0,
                avg_prompt_tokens_per_decision=0.0,
                avg_completion_tokens_per_decision=0.0,
                peak_prompt_tokens=0,
                memory_injected_tokens_total=0,
                decision_count=0,
                parse_success_count=0,
                parse_fallback_count=0,
                parse_error_count=0,
                avg_latency_ms=0.0,
                p99_latency_ms=0.0,
            )

            results = {
                "match": [match_metrics],
                "decision": [],
                "player": [],
            }
            generator = ReportGenerator(results)
            generator.write_all(output_dir)

            assert (output_dir / "match_metrics.csv").exists()
            # decision 和 player 需要对应数据才能生成文件
            assert (output_dir / "reliability_summary.json").exists()
            assert (output_dir / "report.md").exists()

    def test_write_csv_with_match_metrics(self) -> None:
        """write_csv 写入 MatchMetrics。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            match_metrics = MatchMetrics(
                match_id="m1",
                job_id="j1",
                seed=42,
                outcome="completed",
                step_count=100,
                hand_count=10,
                total_duration_ms=5000.0,
                final_points=(35000, 28000, 22000, 15000),
                point_delta=(10000, 3000, -3000, -10000),
                starting_points=(25000, 25000, 25000, 25000),
                ron_count=(1, 0, 0, 0),
                tsumo_count=(0, 1, 0, 0),
                riichi_count=(1, 2, 0, 1),
                riichi_success_count=(1, 1, 0, 1),
                total_prompt_tokens=10000,
                total_completion_tokens=2000,
                avg_prompt_tokens_per_decision=1000.0,
                avg_completion_tokens_per_decision=200.0,
                peak_prompt_tokens=1500,
                memory_injected_tokens_total=500,
                decision_count=10,
                parse_success_count=8,
                parse_fallback_count=2,
                parse_error_count=0,
                avg_latency_ms=100.0,
                p99_latency_ms=200.0,
            )

            results = {"match": [match_metrics], "decision": [], "player": []}
            generator = ReportGenerator(results)
            generator.write_csv(output_dir)

            csv_path = output_dir / "match_metrics.csv"
            assert csv_path.exists()

            # 检查内容
            content = csv_path.read_text()
            assert "match_id" in content
            assert "m1" in content
            assert "completed" in content

    def test_write_csv_with_decision_metrics(self) -> None:
        """write_csv 写入 DecisionMetrics。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            decision_metrics = DecisionMetrics(
                match_id="m1",
                job_id="j1",
                seat=0,
                hand_index=1,
                step_index=10,
                parse_status="ok",
                fallback_used=False,
                latency_ms=100.0,
                prompt_tokens=1000,
                completion_tokens=100,
                memory_injected_tokens=50,
                action_kind="discard",
            )

            results = {"match": [], "decision": [decision_metrics], "player": []}
            generator = ReportGenerator(results)
            generator.write_csv(output_dir)

            csv_path = output_dir / "decision_metrics.csv"
            assert csv_path.exists()

            content = csv_path.read_text()
            assert "match_id" in content
            assert "m1" in content
            assert "ok" in content
            assert "discard" in content

    def test_write_csv_with_player_metrics(self) -> None:
        """write_csv 写入 PlayerMetrics。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            player_metrics = PlayerMetrics(
                seat=0,
                match_count=5,
                avg_final_points=30000.0,
                avg_point_delta=5000.0,
                total_point_delta=25000,
                total_ron_count=3,
                total_tsumo_count=2,
                total_riichi_count=4,
                riichi_success_rate=0.75,
                avg_prompt_tokens=1000.0,
                avg_completion_tokens=200.0,
                total_tokens=6000,
                avg_memory_injected_tokens=50.0,
                total_decisions=50,
                parse_success_rate=0.95,
                avg_latency_ms=100.0,
                p99_latency_ms=200.0,
            )

            results = {"match": [], "decision": [], "player": [player_metrics]}
            generator = ReportGenerator(results)
            generator.write_csv(output_dir)

            csv_path = output_dir / "player_metrics.csv"
            assert csv_path.exists()

            content = csv_path.read_text()
            assert "seat" in content
            assert "0" in content
            assert "match_count" in content

    def test_write_json_creates_reliability_summary(self) -> None:
        """write_json 创建可靠性摘要。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            decision_metrics = [
                DecisionMetrics(
                    match_id="m1",
                    job_id="j1",
                    seat=0,
                    hand_index=1,
                    step_index=10,
                    parse_status="ok",
                    fallback_used=False,
                    latency_ms=100.0,
                    prompt_tokens=1000,
                    completion_tokens=100,
                    memory_injected_tokens=50,
                    action_kind="discard",
                ),
                DecisionMetrics(
                    match_id="m1",
                    job_id="j1",
                    seat=1,
                    hand_index=1,
                    step_index=20,
                    parse_status="fallback",
                    fallback_used=True,
                    latency_ms=150.0,
                    prompt_tokens=2000,
                    completion_tokens=200,
                    memory_injected_tokens=100,
                    action_kind="draw",
                ),
            ]

            results = {"match": [], "decision": decision_metrics, "player": []}
            generator = ReportGenerator(results)
            generator.write_json(output_dir)

            json_path = output_dir / "reliability_summary.json"
            assert json_path.exists()

            content = json.loads(json_path.read_text())
            assert content["total_decisions"] == 2
            assert content["parse_success_count"] == 1
            assert content["parse_fallback_count"] == 1
            assert content["parse_success_rate"] == 0.5
            assert content["avg_latency_ms"] == 125.0

    def test_write_markdown_creates_report(self) -> None:
        """write_markdown 创建报告。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            match_metrics = MatchMetrics(
                match_id="m1",
                job_id="j1",
                seed=42,
                outcome="completed",
                step_count=100,
                hand_count=10,
                total_duration_ms=5000.0,
                final_points=(35000, 28000, 22000, 15000),
                point_delta=(10000, 3000, -3000, -10000),
                starting_points=(25000, 25000, 25000, 25000),
                ron_count=(1, 0, 0, 0),
                tsumo_count=(0, 1, 0, 0),
                riichi_count=(1, 2, 0, 1),
                riichi_success_count=(1, 1, 0, 1),
                total_prompt_tokens=10000,
                total_completion_tokens=2000,
                avg_prompt_tokens_per_decision=1000.0,
                avg_completion_tokens_per_decision=200.0,
                peak_prompt_tokens=1500,
                memory_injected_tokens_total=500,
                decision_count=10,
                parse_success_count=8,
                parse_fallback_count=2,
                parse_error_count=0,
                avg_latency_ms=100.0,
                p99_latency_ms=200.0,
            )

            player_metrics = PlayerMetrics(
                seat=0,
                match_count=5,
                avg_final_points=30000.0,
                avg_point_delta=5000.0,
                total_point_delta=25000,
                total_ron_count=3,
                total_tsumo_count=2,
                total_riichi_count=4,
                riichi_success_rate=0.75,
                avg_prompt_tokens=1000.0,
                avg_completion_tokens=200.0,
                total_tokens=6000,
                avg_memory_injected_tokens=50.0,
                total_decisions=50,
                parse_success_rate=0.95,
                avg_latency_ms=100.0,
                p99_latency_ms=200.0,
            )

            results = {"match": [match_metrics], "decision": [], "player": [player_metrics]}
            generator = ReportGenerator(results)
            generator.write_markdown(output_dir)

            md_path = output_dir / "report.md"
            assert md_path.exists()

            content = md_path.read_text()
            assert "# Metrics Report" in content
            assert "## Match Summary" in content
            assert "## Player Summary" in content
            assert "## Reliability Summary" in content

    def test_empty_results_creates_empty_files(self) -> None:
        """空结果创建空文件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            results = {"match": [], "decision": [], "player": []}
            generator = ReportGenerator(results)
            generator.write_all(output_dir)

            # 检查可靠性摘要
            json_path = output_dir / "reliability_summary.json"
            content = json.loads(json_path.read_text())
            assert content["total_decisions"] == 0
            assert content["parse_success_rate"] == 1.0  # 无决策时默认 1.0

    def test_percentile_calculation(self) -> None:
        """百分位数计算。"""
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

        # percentile 使用 idx = int(n * p / 100)
        # p50: idx = int(10 * 50 / 100) = 5, values[5] = 60.0
        p50 = ReportGenerator._percentile(values, 50)
        assert p50 == 60.0

        # p99: idx = int(10 * 99 / 100) = 9, values[9] = 100.0
        p99 = ReportGenerator._percentile(values, 99)
        assert p99 == 100.0

    def test_percentile_empty_values(self) -> None:
        """空值百分位数返回 0。"""
        result = ReportGenerator._percentile([], 50)
        assert result == 0.0

    def test_creates_parent_directory(self) -> None:
        """创建父目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "dir"

            results = {"match": [], "decision": [], "player": []}
            generator = ReportGenerator(results)
            generator.write_all(output_dir)

            assert output_dir.exists()

    def test_handles_over_budget_matches(self) -> None:
        """处理超预算 match。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # 创建超预算 match（avg_prompt_tokens > 5000）
            match_metrics = MatchMetrics(
                match_id="m1",
                job_id="j1",
                seed=42,
                outcome="completed",
                step_count=100,
                hand_count=10,
                total_duration_ms=5000.0,
                final_points=(35000, 28000, 22000, 15000),
                point_delta=(10000, 3000, -3000, -10000),
                starting_points=(25000, 25000, 25000, 25000),
                ron_count=(0, 0, 0, 0),
                tsumo_count=(0, 0, 0, 0),
                riichi_count=(0, 0, 0, 0),
                riichi_success_count=(0, 0, 0, 0),
                total_prompt_tokens=60000,
                total_completion_tokens=2000,
                avg_prompt_tokens_per_decision=6000.0,  # > 5000
                avg_completion_tokens_per_decision=200.0,
                peak_prompt_tokens=6500,
                memory_injected_tokens_total=500,
                decision_count=10,
                parse_success_count=10,
                parse_fallback_count=0,
                parse_error_count=0,
                avg_latency_ms=100.0,
                p99_latency_ms=200.0,
            )

            results = {"match": [match_metrics], "decision": [], "player": []}
            generator = ReportGenerator(results)
            generator.write_json(output_dir)

            json_path = output_dir / "reliability_summary.json"
            content = json.loads(json_path.read_text())
            assert content["matches_with_over_budget"] == 1
            assert content["over_budget_rate"] == 1.0


class TestReliabilitySummary:
    """可靠性摘要测试。"""

    def test_aggregates_from_multiple_decisions(self) -> None:
        """从多个决策聚合。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            decision_metrics = [
                DecisionMetrics(
                    match_id="m1",
                    job_id="j1",
                    seat=0,
                    hand_index=1,
                    step_index=10,
                    parse_status="ok",
                    fallback_used=False,
                    latency_ms=100.0,
                    prompt_tokens=1000,
                    completion_tokens=100,
                    memory_injected_tokens=50,
                    action_kind="discard",
                ),
                DecisionMetrics(
                    match_id="m1",
                    job_id="j1",
                    seat=1,
                    hand_index=1,
                    step_index=20,
                    parse_status="ok",
                    fallback_used=False,
                    latency_ms=200.0,
                    prompt_tokens=2000,
                    completion_tokens=200,
                    memory_injected_tokens=100,
                    action_kind="discard",
                ),
                DecisionMetrics(
                    match_id="m1",
                    job_id="j1",
                    seat=2,
                    hand_index=1,
                    step_index=30,
                    parse_status="error",
                    fallback_used=False,
                    latency_ms=300.0,
                    prompt_tokens=3000,
                    completion_tokens=300,
                    memory_injected_tokens=150,
                    action_kind="discard",
                ),
            ]

            results = {"match": [], "decision": decision_metrics, "player": []}
            generator = ReportGenerator(results)
            generator.write_json(output_dir)

            json_path = output_dir / "reliability_summary.json"
            content = json.loads(json_path.read_text())

            assert content["total_decisions"] == 3
            assert content["parse_success_count"] == 2
            assert content["parse_error_count"] == 1
            assert content["avg_prompt_tokens"] == 2000.0
            assert content["avg_completion_tokens"] == 200.0
            assert content["avg_memory_injected_tokens"] == 100.0

    def test_handles_none_values_in_decisions(self) -> None:
        """处理决策中的 None 值。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            decision_metrics = DecisionMetrics(
                match_id="m1",
                job_id="j1",
                seat=0,
                hand_index=1,
                step_index=10,
                parse_status="ok",
                fallback_used=False,
                latency_ms=None,
                prompt_tokens=None,
                completion_tokens=None,
                memory_injected_tokens=None,
                action_kind="discard",
            )

            results = {"match": [], "decision": [decision_metrics], "player": []}
            generator = ReportGenerator(results)
            generator.write_json(output_dir)

            json_path = output_dir / "reliability_summary.json"
            content = json.loads(json_path.read_text())

            assert content["total_decisions"] == 1
            assert content["avg_latency_ms"] == 0.0
            assert content["avg_prompt_tokens"] == 0.0

    def test_skips_non_metric_objects(self) -> None:
        """跳过非 Metric 对象。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # 混合对象类型
            results = {
                "match": [None, {"not": "a metric"}],
                "decision": [None, "not a metric"],
                "player": [],
            }
            generator = ReportGenerator(results)
            generator.write_json(output_dir)

            json_path = output_dir / "reliability_summary.json"
            content = json.loads(json_path.read_text())

            # 应忽略非 Metric 对象
            assert content["total_decisions"] == 0


class TestMarkdownFormatting:
    """Markdown 格式化测试。"""

    def test_limits_match_display_to_10(self) -> None:
        """限制 match 显示数量为 10。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # 创建 15 个 match
            match_metrics = []
            for i in range(15):
                match_metrics.append(
                    MatchMetrics(
                        match_id=f"m{i}",
                        job_id=f"j{i}",
                        seed=42 + i,
                        outcome="completed",
                        step_count=100,
                        hand_count=10,
                        total_duration_ms=5000.0,
                        final_points=(25000, 25000, 25000, 25000),
                        point_delta=(0, 0, 0, 0),
                        starting_points=(25000, 25000, 25000, 25000),
                        ron_count=(0, 0, 0, 0),
                        tsumo_count=(0, 0, 0, 0),
                        riichi_count=(0, 0, 0, 0),
                        riichi_success_count=(0, 0, 0, 0),
                        total_prompt_tokens=0,
                        total_completion_tokens=0,
                        avg_prompt_tokens_per_decision=0.0,
                        avg_completion_tokens_per_decision=0.0,
                        peak_prompt_tokens=0,
                        memory_injected_tokens_total=0,
                        decision_count=0,
                        parse_success_count=0,
                        parse_fallback_count=0,
                        parse_error_count=0,
                        avg_latency_ms=0.0,
                        p99_latency_ms=0.0,
                    )
                )

            results = {"match": match_metrics, "decision": [], "player": []}
            generator = ReportGenerator(results)
            generator.write_markdown(output_dir)

            md_path = output_dir / "report.md"
            content = md_path.read_text()

            assert "and 5 more matches" in content

    def test_formats_player_table(self) -> None:
        """格式化 player 表格。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            player_metrics = [
                PlayerMetrics(
                    seat=0,
                    match_count=5,
                    avg_final_points=30000.0,
                    avg_point_delta=5000.0,
                    total_point_delta=25000,
                    total_ron_count=3,
                    total_tsumo_count=2,
                    total_riichi_count=4,
                    riichi_success_rate=0.75,
                    avg_prompt_tokens=1000.0,
                    avg_completion_tokens=200.0,
                    total_tokens=6000,
                    avg_memory_injected_tokens=50.0,
                    total_decisions=50,
                    parse_success_rate=0.95,
                    avg_latency_ms=100.0,
                    p99_latency_ms=200.0,
                ),
            ]

            results = {"match": [], "decision": [], "player": player_metrics}
            generator = ReportGenerator(results)
            generator.write_markdown(output_dir)

            md_path = output_dir / "report.md"
            content = md_path.read_text()

            assert "| Seat | Matches |" in content
            assert "| 0 | 5 |" in content