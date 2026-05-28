"""DecisionScreen - 单个决策详情页面。"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from metrics.loader import DecisionRecord
from ui.viewer.screens.base import BaseScreen

if TYPE_CHECKING:
    from textual.widget import Widget


class DecisionScreen(BaseScreen):
    """单个决策详情页面。

    显示 action, legal_actions, diagnostics, latency 等信息。
    """

    TITLE = "决策详情"
    SUBTITLE = "Decision Detail"

    def __init__(
        self,
        decision: DecisionRecord,
        *,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """初始化决策详情页面。

        Args:
            decision: 决策记录
            name: Screen 名称
            id: Screen ID
        """
        super().__init__(name=name, id=id)
        self._decision = decision

    def compose(self) -> Generator[Widget, None, None]:
        """构建界面布局。"""
        yield Static(self.build_header())

        with Horizontal():
            with Vertical(id="decision-left"):
                yield Static(id="decision-meta")
                yield Static(id="decision-action")
            with Vertical(id="decision-right"):
                yield Static(id="decision-legal")
                yield Static(id="decision-diagnostics")

        yield Static(id="status-line")

    async def on_mount(self) -> None:
        """挂载时渲染内容。"""
        self._render_meta()
        self._render_action()
        self._render_legal_actions()
        self._render_diagnostics()
        self.set_status("按 Q 返回")

    def _render_meta(self) -> None:
        """渲染元数据。"""
        meta_widget = self.query_one("#decision-meta", Static)
        d = self._decision

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("label", style="dim")
        table.add_column("value")

        table.add_row("Match ID", d.match_id)
        table.add_row("Step Index", str(d.step_index))
        table.add_row("Seat", ["E", "S", "W", "N"][d.seat] if 0 <= d.seat < 4 else str(d.seat))

        # 解析状态
        status_style = "green" if d.parse_status == "ok" else "yellow" if d.parse_status == "fallback" else "red"
        table.add_row("Parse Status", Text(d.parse_status, style=status_style))

        # Fallback
        fallback_text = "Yes" if d.fallback_used else "No"
        fallback_style = "yellow" if d.fallback_used else "dim"
        table.add_row("Fallback Used", Text(fallback_text, style=fallback_style))

        # 延迟
        if d.latency_ms is not None:
            table.add_row("Latency", f"{d.latency_ms:.1f}ms")

        meta_widget.update(
            Panel(
                table,
                title="Meta",
                border_style=self.BORDER_STYLE,
            )
        )

    def _render_action(self) -> None:
        """渲染 action 详情。"""
        action_widget = self.query_one("#decision-action", Static)
        action = self._decision.action

        if not action:
            action_widget.update(Panel("无 action 数据", title="Action", border_style="dim"))
            return

        # 格式化为 JSON
        action_json = json.dumps(action, indent=2, ensure_ascii=False)
        syntax = Syntax(action_json, "json", theme="monokai", line_numbers=False)

        action_widget.update(
            Panel(
                syntax,
                title="Action",
                border_style=self.BORDER_STYLE,
            )
        )

    def _render_legal_actions(self) -> None:
        """渲染 legal_actions。"""
        legal_widget = self.query_one("#decision-legal", Static)
        legal_actions = self._decision.diagnostics.get("legal_actions", [])

        if not legal_actions:
            legal_widget.update(Panel("无 legal_actions 数据", title="Legal Actions", border_style="dim"))
            return

        # 显示 legal actions 列表
        if isinstance(legal_actions, list):
            # 构建表格
            table = Table(show_edge=False)
            table.add_column("#", justify="right", style="dim", width=4)
            table.add_column("Type", style="white")
            table.add_column("Details", style="dim")

            for i, action in enumerate(legal_actions[:20]):  # 最多显示 20 个
                if isinstance(action, dict):
                    action_type = action.get("type", "unknown")
                    details = self._format_action_details(action)
                    table.add_row(str(i), action_type, details)
                else:
                    table.add_row(str(i), str(action), "")

            if len(legal_actions) > 20:
                table.add_row("...", f"({len(legal_actions) - 20} more)", "")

            legal_widget.update(
                Panel(
                    table,
                    title=f"Legal Actions ({len(legal_actions)} total)",
                    border_style=self.BORDER_STYLE,
                )
            )
        else:
            # 非列表类型，直接显示
            legal_json = json.dumps(legal_actions, indent=2, ensure_ascii=False)
            syntax = Syntax(legal_json, "json", theme="monokai", line_numbers=False)
            legal_widget.update(
                Panel(
                    syntax,
                    title="Legal Actions",
                    border_style=self.BORDER_STYLE,
                )
            )

    def _render_diagnostics(self) -> None:
        """渲染 diagnostics。"""
        diagnostics_widget = self.query_one("#decision-diagnostics", Static)
        diagnostics = self._decision.diagnostics

        if not diagnostics:
            diagnostics_widget.update(Panel("无 diagnostics 数据", title="Diagnostics", border_style="dim"))
            return

        # 排除 legal_actions (已单独显示)
        filtered_diagnostics = {k: v for k, v in diagnostics.items() if k != "legal_actions"}

        if not filtered_diagnostics:
            diagnostics_widget.update(Panel("无其他 diagnostics 数据", title="Diagnostics", border_style="dim"))
            return

        # 格式化为 JSON
        diag_json = json.dumps(filtered_diagnostics, indent=2, ensure_ascii=False)
        syntax = Syntax(diag_json, "json", theme="monokai", line_numbers=False)

        diagnostics_widget.update(
            Panel(
                syntax,
                title="Diagnostics",
                border_style=self.BORDER_STYLE,
            )
        )

    def _format_action_details(self, action: dict[str, Any]) -> str:
        """格式化 action 详情。

        Args:
            action: action 字典

        Returns:
            格式化后的详情字符串
        """
        parts: list[str] = []

        # 常见字段
        detail_keys = ["tile", "tiles", "target", "call_type", "hand", "draw"]
        for key in detail_keys:
            if key in action:
                value = action[key]
                if isinstance(value, list):
                    value = ",".join(str(v) for v in value)
                parts.append(f"{key}={value}")

        return ", ".join(parts[:3])  # 最多显示 3 个字段