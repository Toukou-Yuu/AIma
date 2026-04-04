"""角色管理逻辑."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import menu
from .utils import (
    PLAYERS_DIR,
    create_profile,
    list_profiles,
    load_profile_data,
    load_profile_stats,
    truncate_text,
)

console = Console()


def run() -> None:
    """运行角色管理菜单循环."""
    while True:
        profiles = list_profiles()
        choice = menu.show_profile_menu(profiles)

        if choice == "back" or choice is None:
            break
        elif choice == "create":
            create_profile_wizard()
        elif choice.startswith("view:"):
            view_profile(choice.split(":", 1)[1])


def create_profile_wizard() -> None:
    """创建角色向导."""
    console.print()
    console.print(Panel("创建新角色", border_style="bright_green"))

    # 步骤 1: ID
    player_id = menu.input_text(
        "角色标识 (用于文件夹名，如: ichihime_v2):",
    )

    if not player_id:
        return

    if not player_id.isalnum():
        console.print("[red]错误: 只能使用字母和数字[/red]")
        menu.press_any_key()
        return

    # 检查是否已存在
    if (PLAYERS_DIR / player_id).exists():
        console.print(f"[red]错误: 角色 '{player_id}' 已存在[/red]")
        menu.press_any_key()
        return

    # 步骤 2: 名称
    name = menu.input_text(
        "显示名称 (牌桌上的名字):",
        default=player_id,
    ) or player_id

    # 步骤 3: 选择模板
    template_choice = menu.select_template()
    if not template_choice:
        return

    # 步骤 4: 是否自定义 prompt
    from .utils import PERSONA_TEMPLATES

    default_persona = PERSONA_TEMPLATES[template_choice]["persona"]
    customize = menu.confirm(
        f"是否自定义人格描述? (默认: {default_persona[:30]}...)",
        default=False,
    )

    custom_persona = None
    if customize:
        custom_persona = menu.multiline_input("输入自定义人格描述:")

    # 创建
    try:
        path = create_profile(player_id, name, template_choice, custom_persona)
        console.print(f"[green]✓ 角色 '{name}' 已创建![/green]")
        console.print(f"  [dim]{path}[/dim]")
    except Exception as e:
        console.print(f"[red]创建失败: {e}[/red]")

    menu.press_any_key()


def view_profile(player_id: str) -> None:
    """查看角色详情."""
    profile = load_profile_data(player_id)

    if profile is None:
        console.print("[red]角色配置不存在[/red]")
        menu.press_any_key()
        return

    console.print()
    console.print(Panel(f"🀄 {profile.get('name', player_id)}", border_style="bright_magenta"))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()

    table.add_row("ID:", player_id)

    # 兼容两种字段名
    persona = profile.get("persona") or profile.get("persona_prompt", "")
    strategy = profile.get("strategy") or profile.get("strategy_prompt", "")

    table.add_row("人格:", truncate_text(persona, 50))
    table.add_row("策略:", truncate_text(strategy, 50))

    console.print(table)

    console.print("\n[bold]统计:[/bold]")
    show_profile_stats(player_id)

    menu.press_any_key()


def show_profile_stats(player_id: str) -> None:
    """显示角色统计."""
    stats = load_profile_stats(player_id)

    if stats is None:
        console.print("  [dim]暂无统计数据[/dim]")
        return

    if stats.get("total_games", 0) == 0:
        console.print("  [dim]暂无对局记录[/dim]")
        return

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()

    total_games = stats["total_games"]
    total_hands = stats["total_hands"]

    table.add_row("对局数:", str(total_games))
    table.add_row(
        "和了:",
        f"{stats['wins']} ({stats['wins'] / max(total_hands, 1) * 100:.1f}%)"
    )
    table.add_row(
        "放铳:",
        f"{stats['deal_ins']} ({stats['deal_ins'] / max(total_hands, 1) * 100:.1f}%)"
    )
    table.add_row(
        "立直:",
        f"{stats['riichi_count']} ({stats['riichi_count'] / max(total_hands, 1) * 100:.1f}%)"
    )
    table.add_row(
        "场均得点:",
        f"{stats['total_points'] / max(total_games, 1):+.0f}"
    )

    console.print(table)
