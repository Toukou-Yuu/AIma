"""DecisionTable Widget - 决策表格组件。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from metrics.loader import DecisionRecord

if TYPE_CHECKING:
    pass


class DecisionTable(Static):
    """决策表格 widget。

    接收 DecisionRecord 列表并渲染为表格，显示 parse_status, fallback_used, action_kind 等。
    """

    DEFAULT_CSS = """
    DecisionTable {
        height: auto;
        max-height: 20;
    }
    """

    # 座位名称映射
    SEAT_NAMES = ["E", "S", "W", "N"]

    def __init__(
        self,
        decisions: list[DecisionRecord],
        *,
        title: str = "Decisions",
        max_display: int = 25,
        show_latency: bool = True,
        show_tokens: bool = False,
        on_select: callable | None = None,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """初始化决策表格。

        Args:
            decisions: 决策记录列表
            title: 面板标题
            max_display: 最大显示数量
            show_latency: 是否显示延迟列
            show_tokens: 是否显示 token 列
            on_select: 选择回调函数 (decision: DecisionRecord) -> None
            name: Widget 名称
            id: Widget ID
        """
        super().__init__(name=name, id=id)
        self._decisions = decisions
        self._title = title
        self._max_display = max_display
        self._show_latency = show_latency
        self._show_tokens = show_tokens
        self._on_select = on_select

    def on_mount(self) -> None:
        """挂载时渲染内容。"""
        self._render_decisions()

    def _render_decisions(self) -> None:
        """渲染决策表格。"""
        if not self._decisions:
            self.update(Panel("无决策记录", title=self._title, border_style="dim"))
            return

        total = len(self._decisions)
        table = Table(title=f"{self._title} ({total} total)", show_edge=False)
        table.add_column("Step", justify="right", style="cyan", width=6)
        table.add_column("Seat", justify="center", width=4)
        table.add_column("Action", style="green")
        table.add_column("Status", justify="center", width=8)
        table.add_column("Fallback", justify="center", width=8)

        if self._show_latency:
            table.add_column("Latency", justify="right", width=8)

        if self._show_tokens:
            table.add_column("Tokens", justify="right", width=8)

        # 只显示前 max_display 个决策
        display_decisions = self._decisions[: self._max_display]

        for decision in display_decisions:
            self._add_decision_row(table, decision)

        if total > self._max_display:
            remaining = total - self._max_display
            empty_cells = [""] * (4 + int(self._show_latency) + int(self._show_tokens))
            table.add_row("...", f"({remaining} more)", *empty_cells[2:])

        self.update(
            Panel(
                table,
                title=self._title,
                border_style="bright_cyan",
            )
        )

    def _add_decision_row(self, table: Table, decision: DecisionRecord) -> None:
        """添加决策行到表格。

        Args:
            table: 目标表格
            decision: 决策记录
        """
        action_type = decision.action.get("type", "unknown")
        seat = self.SEAT_NAMES[decision.seat] if 0 <= decision.seat < 4 else str(decision.seat)

        # 状态样式
        status_style = "green" if decision.parse_status == "ok" else "yellow" if decision.parse_status == "fallback" else "red"
        status = Text(decision.parse_status, style=status_style)

        # Fallback 标记
        fallback = "Y" if decision.fallback_used else "N"
        fallback_style = "yellow" if decision.fallback_used else "dim"
        fallback_text = Text(fallback, style=fallback_style)

        # 延迟
        latency = f"{decision.latency_ms:.0f}ms" if decision.latency_ms else "-"
        latency_text = Text(latency, style="dim")

        # Tokens
        tokens = "-"
        if decision.diagnostics:
            prompt = decision.diagnostics.get("prompt_tokens", 0) or 0
            completion = decision.diagnostics.get("completion_tokens", 0) or 0
            if prompt or completion:
                tokens = f"{prompt + completion}"

        # 构建行
        row: list[str | Text] = [
            str(decision.step_index),
            seat,
            action_type,
            status,
            fallback_text,
        ]

        if self._show_latency:
            row.append(latency_text)

        if self._show_tokens:
            row.append(tokens)

        table.add_row(*row)

    def update_decisions(self, decisions: list[DecisionRecord]) -> None:
        """更新决策列表。

        Args:
            decisions: 新的决策记录列表
        """
        self._decisions = decisions
        self._render_decisions()