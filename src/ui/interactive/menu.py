"""菜单显示逻辑."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import questionary

console = Console()


def show_main_menu() -> str:
    """显示主菜单，返回选择."""
    console.print()
    console.print(
        Panel(
            Text.assemble(
                ("AIma", "bold bright_cyan"),
                (" 麻将 AI 终端", "bright_white"),
            ),
            border_style="bright_cyan",
            padding=(1, 0),
        )
    )

    return questionary.select(
        "",
        choices=[
            questionary.Choice("🎮 快速开始 (Dry-run 演示)", value="quick"),
            questionary.Choice("🀄 开始对局", value="match"),
            questionary.Choice("👤 角色管理", value="profile"),
            questionary.Choice("📺 牌谱回放", value="replay"),
            questionary.Separator(),
            questionary.Choice("❌ 退出", value="quit"),
        ],
        qmark="",
        pointer="▸",
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask() or "quit"


def show_profile_menu(profiles: list[dict]) -> str | None:
    """显示角色管理菜单."""
    choices = []
    for p in profiles:
        label = f"🀄 {p['name']}"
        choices.append(questionary.Choice(label, value=f"view:{p['id']}"))

    choices.extend([
        questionary.Separator(),
        questionary.Choice("➕ 创建新角色", value="create"),
        questionary.Separator(),
        questionary.Choice("🔙 返回主菜单", value="back"),
    ])

    console.print()
    return questionary.select(
        "角色管理",
        choices=choices,
        qmark="",
        pointer="▸",
    ).ask()


def show_replay_menu(replays: list[tuple[str, Path]]) -> str | None:
    """显示牌谱回放菜单."""
    choices = []
    for label, path in replays:
        choices.append(questionary.Choice(label, value=str(path)))

    choices.extend([
        questionary.Separator(),
        questionary.Choice("🔙 返回", value="back"),
    ])

    console.print()
    return questionary.select(
        "选择牌谱回放:",
        choices=choices,
        qmark="",
        pointer="▸",
    ).ask()


def confirm(message: str, default: bool = True) -> bool:
    """确认对话框."""
    return questionary.confirm(message, default=default).ask() or False


def input_text(message: str, default: str = "") -> str:
    """文本输入."""
    return questionary.text(message, default=default).ask() or ""


def input_number(message: str, default: str = "0") -> str:
    """数字输入."""
    return questionary.text(message, default=default).ask() or default


def select_player_for_seat(seat_name: str, profiles: list[dict]) -> str | None:
    """为座位选择玩家."""
    choices = [
        questionary.Choice("🤖 默认 AI (dry-run)", value="default"),
        questionary.Separator(),
    ]
    for p in profiles:
        choices.append(questionary.Choice(f"🀄 {p['name']}", value=p["id"]))

    return questionary.select(
        f"选择 {seat_name}:",
        choices=choices,
        qmark="",
        pointer="▸",
    ).ask()


def press_any_key() -> None:
    """按任意键继续."""
    questionary.press_any_key_to_continue().ask()


def select_template() -> str | None:
    """选择人格模板."""
    from .utils import PERSONA_TEMPLATES

    return questionary.select(
        "选择人格模板:",
        choices=[
            questionary.Choice(
                f"🗡️  {PERSONA_TEMPLATES['aggressive']['name']}",
                value="aggressive"
            ),
            questionary.Choice(
                f"🛡️  {PERSONA_TEMPLATES['defensive']['name']}",
                value="defensive"
            ),
            questionary.Choice(
                f"⚖️  {PERSONA_TEMPLATES['balanced']['name']}",
                value="balanced"
            ),
            questionary.Choice(
                f"🎭 {PERSONA_TEMPLATES['adaptive']['name']}",
                value="adaptive"
            ),
        ],
        qmark="",
        pointer="▸",
    ).ask()


def multiline_input(message: str) -> str:
    """多行文本输入."""
    return questionary.text(message, multiline=True).ask() or ""
