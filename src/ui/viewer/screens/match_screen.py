"""MatchScreen: 显示单局对局摘要、事件时间线和决策列表。"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from textual.widgets import Static

from metrics.loader import RunData
from ui.viewer.components.decision_table import DecisionTable
from ui.viewer.components.event_list import EventList
from ui.viewer.data_source import RunDataSource
from ui.viewer.screens.base import BaseScreen

if TYPE_CHECKING:
    from textual.widget import Widget


class MatchScreen(BaseScreen):
    """单局对局摘要界面。"""

    TITLE = "对局摘要"
    SUBTITLE = "Match Summary"

    BINDINGS = [
        ("d", "view_decision", "查看决策"),
        ("m", "view_metrics", "查看指标"),
    ]

    def __init__(
        self,
        data_source: RunDataSource,
        job_id: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.data_source = data_source
        self.job_id = job_id
        self._run_data: RunData | None = None
        self._event_list: EventList | None = None
        self._decision_table: DecisionTable | None = None

    def compose(self) -> Generator[Widget, None, None]:
        """构建界面组件。"""
        yield Static(self.build_header())
        yield Static(id="match-summary")
        yield EventList([], id="events-timeline")
        yield DecisionTable([], id="decisions-list")
        yield Static(id="status-line")

    async def on_mount(self) -> None:
        """加载并显示数据。"""
        self._run_data = self.data_source.load_job(self.job_id)
        if self._run_data is None:
            self.set_status(f"无法加载 job: {self.job_id}", "red")
            return

        self._render_summary()

        # 获取并更新组件
        self._event_list = self.query_one("#events-timeline", EventList)
        self._decision_table = self.query_one("#decisions-list", DecisionTable)

        self._event_list.update_events(self._run_data.events)
        self._decision_table.update_decisions(self._run_data.decisions)

        self.set_status("按 D 查看决策详情 | M 查看指标 | Q 退出")

    def action_view_decision(self) -> None:
        """查看第一个决策详情。"""
        if self._run_data is None or not self._run_data.decisions:
            self.set_status("无决策记录", "yellow")
            return

        from ui.viewer.screens.decision_screen import DecisionScreen

        self.app.push_screen(DecisionScreen(self._run_data.decisions[0]))

    def action_view_metrics(self) -> None:
        """查看指标页面。"""
        from ui.viewer.screens.metrics_screen import MetricsScreen

        # 如果有 run_data，计算 ReliabilitySummary
        reliability = self._compute_reliability()
        self.app.push_screen(MetricsScreen(reliability=reliability))

    def _compute_reliability(self):
        """从 run_data 计算 ReliabilitySummary。"""
        if self._run_data is None or not self._run_data.decisions:
            return None

        from metrics.schema import ReliabilitySummary

        decisions = self._run_data.decisions
        total = len(decisions)

        parse_success = sum(1 for d in decisions if d.parse_status == "ok")
        parse_fallback = sum(1 for d in decisions if d.parse_status == "fallback" or d.fallback_used)
        parse_error = sum(1 for d in decisions if d.parse_status == "error")

        latencies = [d.latency_ms for d in decisions if d.latency_ms is not None]
        latencies.sort()

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        def percentile(sorted_list: list[float], p: float) -> float:
            if not sorted_list:
                return 0.0
            k = (len(sorted_list) - 1) * p
            f = int(k)
            c = f + 1 if f + 1 < len(sorted_list) else f
            return sorted_list[f] + (k - f) * (sorted_list[c] - sorted_list[f])

        # Token 统计
        prompt_tokens = []
        completion_tokens = []
        memory_tokens = []

        for d in decisions:
            diag = d.diagnostics
            if diag:
                if "prompt_tokens" in diag and diag["prompt_tokens"]:
                    prompt_tokens.append(diag["prompt_tokens"])
                if "completion_tokens" in diag and diag["completion_tokens"]:
                    completion_tokens.append(diag["completion_tokens"])
                if "memory_injected_tokens" in diag and diag["memory_injected_tokens"]:
                    memory_tokens.append(diag["memory_injected_tokens"])

        return ReliabilitySummary(
            total_decisions=total,
            parse_success_count=parse_success,
            parse_fallback_count=parse_fallback,
            parse_error_count=parse_error,
            parse_success_rate=parse_success / total if total > 0 else 0.0,
            parse_fallback_rate=parse_fallback / total if total > 0 else 0.0,
            parse_error_rate=parse_error / total if total > 0 else 0.0,
            avg_latency_ms=avg_latency,
            p50_latency_ms=percentile(latencies, 0.5),
            p95_latency_ms=percentile(latencies, 0.95),
            p99_latency_ms=percentile(latencies, 0.99),
            avg_prompt_tokens=sum(prompt_tokens) / len(prompt_tokens) if prompt_tokens else 0.0,
            avg_completion_tokens=sum(completion_tokens) / len(completion_tokens) if completion_tokens else 0.0,
            avg_memory_injected_tokens=sum(memory_tokens) / len(memory_tokens) if memory_tokens else 0.0,
            matches_with_over_budget=0,
            over_budget_rate=0.0,
        )

    def _render_summary(self) -> None:
        """渲染对局摘要。"""
        if self._run_data is None or self._run_data.summary is None:
            return

        summary = self._run_data.summary
        summary_widget = self.query_one("#match-summary", Static)

        # 显示基本信息
        info_table = Table(show_header=False, box=None, padding=(0, 2))
        info_table.add_column("label", style="dim")
        info_table.add_column("value")

        info_table.add_row("Match ID", summary.match_id)
        info_table.add_row("Outcome", summary.outcome)
        info_table.add_row("Steps", str(summary.step_count))
        info_table.add_row("Hands", str(summary.hand_count))

        if summary.duration_ms:
            duration_sec = summary.duration_ms / 1000
            info_table.add_row("Duration", f"{duration_sec:.2f}s")

        if summary.stopped_reason:
            info_table.add_row("Stopped", summary.stopped_reason)

        # 显示最终点数
        points_table = Table(title="Final Points", show_edge=False)
        points_table.add_column("Seat", justify="center")
        points_table.add_column("Points", justify="right")
        points_table.add_column("Delta", justify="right")

        seats = ["East", "South", "West", "North"]
        for i, seat in enumerate(seats):
            delta = summary.point_delta[i]
            delta_str = f"+{delta}" if delta > 0 else str(delta)
            points_table.add_row(seat, str(summary.final_points[i]), delta_str)

        summary_widget.update(
            Panel(
                Group(info_table, points_table),
                title="Match Summary",
                border_style=self.BORDER_STYLE,
            )
        )