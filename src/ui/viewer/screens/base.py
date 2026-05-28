"""Shared screen primitives for viewer."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.screen import Screen
from textual.widgets import Static


class BaseScreen(Screen[None]):
    """Viewer screen 基类。"""

    TITLE = ""
    SUBTITLE = ""
    BORDER_STYLE = "bright_cyan"
    HEADER_WIDTH = 88

    def build_header(self, title: str | None = None, subtitle: str | None = None) -> Panel:
        """构建页面头部。"""
        from rich.align import Align
        from rich.box import ROUNDED
        from rich.console import Group

        header_title = title or self.TITLE
        header_subtitle = subtitle or self.SUBTITLE

        header_lines = [
            Align.center(Text(header_title, style=f"bold {self.BORDER_STYLE}")),
        ]
        if header_subtitle:
            header_lines.append(Align.center(Text(header_subtitle, style="dim")))

        return Panel(
            Group(*header_lines),
            border_style=self.BORDER_STYLE,
            box=ROUNDED,
            width=self.HEADER_WIDTH,
            padding=(0, 2),
            expand=False,
        )

    def set_status(self, message: str, style: str = "dim") -> None:
        """设置状态栏消息。"""
        status = self.query_one("#status-line", Static)
        status.update(Text(message, style=style))