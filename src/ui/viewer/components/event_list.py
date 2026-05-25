"""EventList Widget - 可复用的事件时间线组件。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from textual.widgets import Static

from metrics.loader import EventRecord

if TYPE_CHECKING:
    from rich.text import Text


class EventList(Static):
    """事件时间线 widget。

    接收 EventRecord 列表并渲染为表格形式的时间线。
    """

    DEFAULT_CSS = """
    EventList {
        height: auto;
        max-height: 20;
    }
    """

    def __init__(
        self,
        events: list[EventRecord],
        *,
        title: str = "Events",
        max_display: int = 25,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """初始化事件列表。

        Args:
            events: 事件记录列表
            title: 面板标题
            max_display: 最大显示数量
            name: Widget 名称
            id: Widget ID
        """
        super().__init__(name=name, id=id)
        self._events = events
        self._title = title
        self._max_display = max_display

    def on_mount(self) -> None:
        """挂载时渲染内容。"""
        self._render_events()

    def _render_events(self) -> None:
        """渲染事件时间线。"""
        if not self._events:
            self.update(Panel("无事件记录", title=self._title, border_style="dim"))
            return

        total = len(self._events)
        table = Table(title=f"{self._title} ({total} total)", show_edge=False)
        table.add_column("Step", justify="right", style="cyan", width=6)
        table.add_column("Event Type", style="white")
        table.add_column("Details", style="dim")

        # 只显示前 max_display 个事件
        display_events = self._events[: self._max_display]

        for event in display_events:
            event_type = event.event.get("type", "unknown")
            details = self._format_event_details(event)
            table.add_row(str(event.step_index), event_type, details)

        if total > self._max_display:
            remaining = total - self._max_display
            table.add_row("...", f"({remaining} more)", "")

        self.update(
            Panel(
                table,
                title=self._title,
                border_style="bright_cyan",
            )
        )

    def _format_event_details(self, event: EventRecord) -> str:
        """格式化事件详情。

        Args:
            event: 事件记录

        Returns:
            格式化后的详情字符串
        """
        event_type = event.event.get("type", "")
        parts: list[str] = []

        if event_type == "draw":
            tile = event.event.get("tile", "")
            seat = event.event.get("seat")
            if tile:
                parts.append(f"tile={tile}")
            if seat is not None:
                parts.append(f"seat={seat}")

        elif event_type == "discard":
            tile = event.event.get("tile", "")
            seat = event.event.get("seat")
            if tile:
                parts.append(f"tile={tile}")
            if seat is not None:
                parts.append(f"seat={seat}")

        elif event_type == "call":
            call_type = event.event.get("call_type", "")
            seat = event.event.get("seat")
            if call_type:
                parts.append(f"type={call_type}")
            if seat is not None:
                parts.append(f"seat={seat}")

        elif event_type == "riichi":
            seat = event.event.get("seat")
            if seat is not None:
                parts.append(f"seat={seat}")

        elif event_type == "ron":
            winner = event.event.get("winner")
            loser = event.event.get("loser")
            if winner is not None:
                parts.append(f"winner={winner}")
            if loser is not None:
                parts.append(f"loser={loser}")

        elif event_type == "tsumo":
            winner = event.event.get("winner")
            if winner is not None:
                parts.append(f"winner={winner}")

        elif event_type == "hand_over":
            reason = event.event.get("reason", "")
            if reason:
                parts.append(f"reason={reason}")

        elif event_type == "round_over":
            outcome = event.event.get("outcome", "")
            if outcome:
                parts.append(f"outcome={outcome}")

        # 如果没有提取到详情，显示关键字段
        if not parts:
            keys = ["seat", "tile", "call_type", "outcome", "reason"]
            for key in keys:
                if key in event.event:
                    parts.append(f"{key}={event.event[key]}")

        return ", ".join(parts[:3])  # 最多显示 3 个字段

    def update_events(self, events: list[EventRecord]) -> None:
        """更新事件列表。

        Args:
            events: 新的事件记录列表
        """
        self._events = events
        self._render_events()