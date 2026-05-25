"""MetricsScreen - 指标仪表盘页面。"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Static

from metrics.schema import ReliabilitySummary
from ui.viewer.components.metrics_panel import MetricsPanel
from ui.viewer.screens.base import BaseScreen

if TYPE_CHECKING:
    from textual.widget import Widget


class MetricsScreen(BaseScreen):
    """指标仪表盘页面。

    显示 aggregate/reliability_summary.json 中的数据。
    """

    TITLE = "指标仪表盘"
    SUBTITLE = "Metrics Dashboard"

    def __init__(
        self,
        reliability: ReliabilitySummary | None = None,
        *,
        aggregate_dir: Path | None = None,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """初始化指标页面。

        Args:
            reliability: 可靠性汇总数据 (可选)
            aggregate_dir: aggregate 目录路径 (可选，用于从文件加载)
            name: Screen 名称
            id: Screen ID
        """
        super().__init__(name=name, id=id)
        self._reliability = reliability
        self._aggregate_dir = aggregate_dir
        self._metrics_panel: MetricsPanel | None = None

    def compose(self) -> Generator[Widget, None, None]:
        """构建界面布局。"""
        yield Static(self.build_header())
        yield Static(id="metrics-overview")
        with Vertical(id="metrics-container"):
            yield MetricsPanel(self._reliability, id="reliability-panel")
        yield Static(id="status-line")

    async def on_mount(self) -> None:
        """挂载时加载数据。"""
        # 如果没有提供 reliability，尝试从文件加载
        if self._reliability is None and self._aggregate_dir is not None:
            self._load_reliability_from_file()

        self._render_overview()
        self.set_status("按 Q 返回")

    def _load_reliability_from_file(self) -> None:
        """从文件加载可靠性数据。"""
        if self._aggregate_dir is None:
            return

        summary_path = self._aggregate_dir / "reliability_summary.json"
        if not summary_path.exists():
            return

        try:
            with summary_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            self._reliability = ReliabilitySummary(
                total_decisions=data.get("total_decisions", 0),
                parse_success_count=data.get("parse_success_count", 0),
                parse_fallback_count=data.get("parse_fallback_count", 0),
                parse_error_count=data.get("parse_error_count", 0),
                parse_success_rate=data.get("parse_success_rate", 0.0),
                parse_fallback_rate=data.get("parse_fallback_rate", 0.0),
                parse_error_rate=data.get("parse_error_rate", 0.0),
                avg_latency_ms=data.get("avg_latency_ms", 0.0),
                p50_latency_ms=data.get("p50_latency_ms", 0.0),
                p95_latency_ms=data.get("p95_latency_ms", 0.0),
                p99_latency_ms=data.get("p99_latency_ms", 0.0),
                avg_prompt_tokens=data.get("avg_prompt_tokens", 0.0),
                avg_completion_tokens=data.get("avg_completion_tokens", 0.0),
                avg_memory_injected_tokens=data.get("avg_memory_injected_tokens", 0.0),
                matches_with_over_budget=data.get("matches_with_over_budget", 0),
                over_budget_rate=data.get("over_budget_rate", 0.0),
            )

            # 更新 panel
            panel = self.query_one("#reliability-panel", MetricsPanel)
            panel.update_reliability(self._reliability)

        except (json.JSONDecodeError, OSError, KeyError):
            pass

    def _render_overview(self) -> None:
        """渲染概览信息。"""
        overview_widget = self.query_one("#metrics-overview", Static)

        if self._reliability is None:
            overview_widget.update(
                Panel(
                    Text("无指标数据", style="yellow"),
                    title="Overview",
                    border_style="dim",
                )
            )
            return

        r = self._reliability

        # 简单概览
        info_lines = [
            f"总决策数: {r.total_decisions:,}",
            f"成功率: {r.parse_success_rate * 100:.1f}%",
            f"平均延迟: {r.avg_latency_ms:.1f}ms",
        ]

        overview_widget.update(
            Panel(
                Text("\n".join(info_lines)),
                title="Overview",
                border_style=self.BORDER_STYLE,
            )
        )