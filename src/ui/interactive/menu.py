"""菜单显示逻辑."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.styles import Style
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import questionary

if TYPE_CHECKING:
    from questionary import Choice


console = Console()

# 自定义样式
CUSTOM_STYLE = Style.from_dict({
    "selected": "ansicyan bold",
    "highlighted": "ansicyan bold",
    "pointer": "ansicyan bold",
    "separator": "#666666",  # 深灰
    "question": "#444444",  # 更深灰
    "instruction": "#555555",  # 深灰降低可视度
})


def _create_panel(content: str, width: int = 40) -> Panel:
    """创建统一宽度的面板."""
    return Panel(
        Align.center(content),
        border_style="bright_cyan",
        width=width,
        padding=(0, 1),
    )


def show_main_menu() -> str:
    """显示主菜单，返回选择."""
    console.print()
    title = Text("AIma 麻将 AI 终端", style="bold bright_cyan")
    console.print(_create_panel(title))
    console.print()

    return questionary.select(
        "",
        choices=[
            questionary.Choice("demo演示", value="quick"),
            questionary.Choice("开始对局", value="match"),
            questionary.Choice("角色管理", value="profile"),
            questionary.Choice("牌谱回放", value="replay"),
            questionary.Separator(),
            questionary.Choice("退出", value="quit"),
        ],
        qmark="",
        pointer=">",
        instruction="[上下键选择，回车确认]",
        style=CUSTOM_STYLE,
    ).ask() or "quit"


def show_profile_menu(profiles: list[dict]) -> str | None:
    """显示角色管理菜单."""
    console.print()
    title = Text("角色管理", style="bold bright_cyan")
    console.print(_create_panel(title))
    console.print()

    choices: list[Choice] = []
    for p in profiles:
        choices.append(questionary.Choice(p['name'], value=f"view:{p['id']}"))

    choices.extend([
        questionary.Separator(),
        questionary.Choice("创建新角色", value="create"),
        questionary.Separator(),
        questionary.Choice("返回主菜单", value="back"),
    ])

    return questionary.select(
        "",
        choices=choices,
        qmark="",
        pointer=">",
        instruction="[上下键选择，回车确认]",
        style=CUSTOM_STYLE,
    ).ask()


def show_replay_menu(replays: list[tuple[str, Path]]) -> str | None:
    """显示牌谱回放菜单."""
    console.print()
    title = Text("牌谱回放", style="bold bright_cyan")
    console.print(_create_panel(title))
    console.print()

    choices: list[Choice] = []
    for label, path in replays:
        choices.append(questionary.Choice(label, value=str(path)))

    choices.extend([
        questionary.Separator(),
        questionary.Choice("返回", value="back"),
    ])

    return questionary.select(
        "",
        choices=choices,
        qmark="",
        pointer=">",
        instruction="[上下键选择，回车确认]",
        style=CUSTOM_STYLE,
    ).ask()


def confirm(message: str, default: bool = True) -> bool:
    """确认对话框."""
    return questionary.confirm(
        message,
        default=default,
        qmark="",
        style=CUSTOM_STYLE,
    ).ask() or False


def input_text(message: str, default: str = "") -> str:
    """文本输入."""
    return questionary.text(
        message,
        default=default,
        qmark="",
        style=CUSTOM_STYLE,
    ).ask() or ""


def input_number(message: str, default: str = "0") -> str:
    """数字输入."""
    return questionary.text(
        message,
        default=default,
        qmark="",
        style=CUSTOM_STYLE,
    ).ask() or default


def select_player_for_seat(seat_name: str, profiles: list[dict]) -> str | None:
    """为座位选择玩家."""
    choices: list[Choice] = [
        questionary.Choice("默认 AI (dry-run)", value="default"),
        questionary.Separator(),
    ]
    for p in profiles:
        choices.append(questionary.Choice(p['name'], value=p["id"]))

    return questionary.select(
        "",
        choices=choices,
        qmark="",
        pointer=">",
        instruction=f"[选择 {seat_name}]",
        style=CUSTOM_STYLE,
    ).ask()


def press_any_key() -> None:
    """按任意键继续."""
    questionary.press_any_key_to_continue(message="按任意键继续...").ask()


def select_template() -> str | None:
    """选择人格模板."""
    from .utils import PERSONA_TEMPLATES

    return questionary.select(
        "",
        choices=[
            questionary.Choice(PERSONA_TEMPLATES['aggressive']['name'], value="aggressive"),
            questionary.Choice(PERSONA_TEMPLATES['defensive']['name'], value="defensive"),
            questionary.Choice(PERSONA_TEMPLATES['balanced']['name'], value="balanced"),
            questionary.Choice(PERSONA_TEMPLATES['adaptive']['name'], value="adaptive"),
        ],
        qmark="",
        pointer=">",
        instruction="[上下键选择，回车确认]",
        style=CUSTOM_STYLE,
    ).ask()


def multiline_input(message: str) -> str:
    """多行文本输入."""
    return questionary.text(message, multiline=True, qmark="", style=CUSTOM_STYLE).ask() or ""
