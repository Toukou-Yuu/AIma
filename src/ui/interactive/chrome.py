"""交互式页面的统一视觉组件。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rich.align import Align
from rich.box import ROUNDED
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass(frozen=True, slots=True)
class ActionOption:
    """操作目录中的一项。"""

    value: str
    label: str
    description: str
    badge: str | None = None


def _coerce_text(value: str | RenderableType) -> RenderableType:
    """将字符串包装为 Rich Text，其余值原样返回。"""
    if isinstance(value, str):
        return Text(value)
    return value


def render_page_header(
    title: str,
    *,
    subtitle: str | None = None,
    border_style: str = "bright_cyan",
    width: int = 68,
) -> Panel:
    """渲染统一页面头部。"""
    header_lines: list[RenderableType] = [
        Align.center(Text(title, style=f"bold {border_style}")),
    ]
    if subtitle:
        header_lines.append(Align.center(Text(subtitle, style="dim")))

    return Panel(
        Group(*header_lines),
        border_style=border_style,
        box=ROUNDED,
        width=width,
        padding=(0, 2),
        expand=False,
    )


def render_summary_panel(
    title: str,
    rows: Iterable[tuple[str, str | RenderableType]],
    *,
    border_style: str = "bright_blue",
) -> Panel:
    """渲染摘要信息面板。"""
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column()

    has_rows = False
    for label, value in rows:
        has_rows = True
        grid.add_row(label, _coerce_text(value))

    if not has_rows:
        grid.add_row("状态", Text("暂无数据", style="dim"))

    return Panel(
        grid,
        title=f"[bold {border_style}]{title}[/]",
        border_style=border_style,
        box=ROUNDED,
        padding=(0, 1),
    )


def render_action_catalog(
    title: str,
    options: Iterable[ActionOption],
    *,
    border_style: str = "bright_green",
) -> Panel:
    """渲染操作目录。"""
    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=16, no_wrap=True)
    grid.add_column()

    for option in options:
        label = Text(option.label, style="bold bright_white")
        if option.badge:
            label.append(" ")
            label.append(f"[{option.badge}]", style="dim")
        description = Text(option.description, style="white")
        grid.add_row(label, description)

    return Panel(
        grid,
        title=f"[bold {border_style}]{title}[/]",
        border_style=border_style,
        box=ROUNDED,
        padding=(0, 1),
    )


def render_empty_state(
    title: str,
    message: str,
    *,
    hint: str | None = None,
    border_style: str = "bright_black",
) -> Panel:
    """渲染统一空状态。"""
    body = Text(message, style="white")
    if hint:
        body.append("\n")
        body.append(hint, style="dim")

    return Panel(
        Align.center(body),
        title=f"[bold]{title}[/]",
        border_style=border_style,
        box=ROUNDED,
        padding=(1, 2),
    )


def render_status_bar(
    message: str,
    *,
    border_style: str = "bright_black",
) -> Panel:
    """渲染页面底部状态提示。"""
    return Panel(
        Text(message, style="dim"),
        border_style=border_style,
        box=ROUNDED,
        padding=(0, 1),
    )
