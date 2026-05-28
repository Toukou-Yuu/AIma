"""MetricsPanel Widget - 指标仪表盘组件。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from metrics.schema import ReliabilitySummary

if TYPE_CHECKING:
    pass


class MetricsPanel(Static):
    """指标仪表盘 widget。

    接收 ReliabilitySummary 数据并渲染为指标面板。
    """

    DEFAULT_CSS = """
    MetricsPanel {
        height: auto;
    }
    """

    def __init__(
        self,
        reliability: ReliabilitySummary | None = None,
        *,
        title: str = "Reliability Metrics",
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """初始化指标面板。

        Args:
            reliability: 可靠性汇总数据
            title: 面板标题
            name: Widget 名称
            id: Widget ID
        """
        super().__init__(name=name, id=id)
        self._reliability = reliability
        self._title = title

    def on_mount(self) -> None:
        """挂载时渲染内容。"""
        self._render_metrics()

    def _render_metrics(self) -> None:
        """渲染指标面板。"""
        if self._reliability is None:
            self.update(Panel("无指标数据", title=self._title, border_style="dim"))
            return

        r = self._reliability

        # 解析状态表格
        parse_table = Table(show_header=False, box=None, padding=(0, 2))
        parse_table.add_column("label", style="dim")
        parse_table.add_column("value", justify="right")

        parse_table.add_row("Total Decisions", f"{r.total_decisions:,}")
        parse_table.add_row("Parse Success", Text(f"{r.parse_success_count:,}", style="green"))
        parse_table.add_row("Parse Fallback", Text(f"{r.parse_fallback_count:,}", style="yellow"))
        parse_table.add_row("Parse Error", Text(f"{r.parse_error_count:,}", style="red"))

        # 比率表格
        rate_table = Table(show_header=False, box=None, padding=(0, 2))
        rate_table.add_column("label", style="dim")
        rate_table.add_column("value", justify="right")

        rate_table.add_row("Success Rate", self._format_percent(r.parse_success_rate, "green"))
        rate_table.add_row("Fallback Rate", self._format_percent(r.parse_fallback_rate, "yellow"))
        rate_table.add_row("Error Rate", self._format_percent(r.parse_error_rate, "red"))

        # 延迟表格
        latency_table = Table(show_header=False, box=None, padding=(0, 2))
        latency_table.add_column("label", style="dim")
        latency_table.add_column("value", justify="right")

        latency_table.add_row("Avg Latency", f"{r.avg_latency_ms:.1f}ms")
        latency_table.add_row("P50 Latency", f"{r.p50_latency_ms:.1f}ms")
        latency_table.add_row("P95 Latency", f"{r.p95_latency_ms:.1f}ms")
        latency_table.add_row("P99 Latency", f"{r.p99_latency_ms:.1f}ms")

        # Token 表格
        token_table = Table(show_header=False, box=None, padding=(0, 2))
        token_table.add_column("label", style="dim")
        token_table.add_column("value", justify="right")

        token_table.add_row("Avg Prompt Tokens", f"{r.avg_prompt_tokens:.1f}")
        token_table.add_row("Avg Completion Tokens", f"{r.avg_completion_tokens:.1f}")
        token_table.add_row("Avg Memory Injected", f"{r.avg_memory_injected_tokens:.1f}")

        # 超预算表格
        budget_table = Table(show_header=False, box=None, padding=(0, 2))
        budget_table.add_column("label", style="dim")
        budget_table.add_column("value", justify="right")

        over_budget_text = Text(
            f"{r.matches_with_over_budget}",
            style="red" if r.matches_with_over_budget > 0 else "dim",
        )
        budget_table.add_row("Over Budget Matches", over_budget_text)
        budget_table.add_row("Over Budget Rate", self._format_percent(r.over_budget_rate, "red" if r.over_budget_rate > 0.1 else "dim"))

        # 组合所有表格
        layout_table = Table.grid(padding=1)
        layout_table.add_column(ratio=1)
        layout_table.add_column(ratio=1)

        layout_table.add_row(
            Group(
                Text("Parse Status", style="bold cyan"),
                parse_table,
            ),
            Group(
                Text("Rates", style="bold cyan"),
                rate_table,
            ),
        )
        layout_table.add_row(
            Group(
                Text("Latency", style="bold cyan"),
                latency_table,
            ),
            Group(
                Text("Tokens", style="bold cyan"),
                token_table,
            ),
        )
        layout_table.add_row(
            Group(
                Text("Budget", style="bold cyan"),
                budget_table,
            ),
            "",
        )

        self.update(
            Panel(
                layout_table,
                title=self._title,
                border_style="bright_cyan",
            )
        )

    def _format_percent(self, value: float, style: str = "white") -> Text:
        """格式化百分比。

        Args:
            value: 小数值 (0.0 - 1.0)
            style: 样式

        Returns:
            格式化后的 Text 对象
        """
        return Text(f"{value * 100:.1f}%", style=style)

    def update_reliability(self, reliability: ReliabilitySummary) -> None:
        """更新可靠性数据。

        Args:
            reliability: 新的可靠性汇总数据
        """
        self._reliability = reliability
        self._render_metrics()