"""角色管理 - 使用统一框架重构."""

from __future__ import annotations

from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ui.interactive.framework import MenuPage, Page, Prompt
from ui.interactive.utils import (
    PLAYERS_DIR,
    create_profile,
    list_profiles,
    load_profile_data,
    load_profile_stats,
)

console = Console()


class ProfileMenuPage(MenuPage):
    """角色管理菜单."""

    title = "角色管理"

    def _get_choices(self):
        import questionary
        profiles = list_profiles()
        choices = []
        for p in profiles:
            choices.append(questionary.Choice(p['name'], value=f"view:{p['id']}"))
        choices.extend([
            questionary.Separator(),
            questionary.Choice("创建新角色", value="create"),
            questionary.Separator(),
            questionary.Choice("返回主菜单", value="back"),
        ])
        return choices


class ProfileDetailPage(Page):
    """角色详情页."""

    border_style = "bright_magenta"

    def __init__(self, player_id: str):
        self.player_id = player_id
        profile = load_profile_data(player_id)
        self.title = f"🀄 {profile.get('name', player_id)}" if profile else "角色详情"

    def _render_content(self) -> None:
        profile = load_profile_data(self.player_id)
        if profile is None:
            console.print("[red]角色配置不存在[/red]")
            Prompt.press_any_key()
            return

        # 兼容两种字段名
        persona = profile.get("persona") or profile.get("persona_prompt", "")
        strategy = profile.get("strategy") or profile.get("strategy_prompt", "")

        # 显示信息
        from rich.console import Group
        info = Group(
            f"[dim]ID:[/dim]      {self.player_id}",
            "",
            f"[dim]人格:[/dim]    {persona}",
            "",
            f"[dim]策略:[/dim]    {strategy}",
        )
        console.print(info)

        console.print("\n[bold]统计:[/bold]")
        self._show_stats()
        Prompt.press_any_key()

    def _show_stats(self) -> None:
        stats = load_profile_stats(self.player_id)
        if stats is None or stats.get("total_games", 0) == 0:
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


class CreateProfilePage(Page):
    """创建角色页."""

    title = "创建新角色"
    border_style = "bright_green"

    def _render_content(self) -> None:
        from .utils import PERSONA_TEMPLATES

        # 步骤 1: ID
        player_id = Prompt.text("角色标识 (用于文件夹名，如: ichihime_v2):")
        if not player_id:
            return

        if not player_id.isalnum():
            console.print("[red]错误: 只能使用字母和数字[/red]")
            Prompt.press_any_key()
            return

        if (PLAYERS_DIR / player_id).exists():
            console.print(f"[red]错误: 角色 '{player_id}' 已存在[/red]")
            Prompt.press_any_key()
            return

        # 步骤 2: 名称
        name = Prompt.text("显示名称 (牌桌上的名字):", default=player_id) or player_id

        # 步骤 3: 选择模板
        template_choice = self._select_template()
        if not template_choice:
            return

        # 步骤 4: 是否自定义 prompt
        default_persona = PERSONA_TEMPLATES[template_choice]["persona"]
        customize = Prompt.confirm(
            f"是否自定义人格描述? (默认: {default_persona[:30]}...)",
            default=False,
        )

        custom_persona = None
        if customize:
            custom_persona = Prompt.multiline("输入自定义人格描述:")

        # 创建
        try:
            path = create_profile(player_id, name, template_choice, custom_persona)
            console.print(f"[green]✓ 角色 '{name}' 已创建![/green]")
            console.print(f"  [dim]{path}[/dim]")
        except Exception as e:
            console.print(f"[red]创建失败: {e}[/red]")

        Prompt.press_any_key()

    def _select_template(self) -> str | None:
        """选择人格模板."""
        from .utils import PERSONA_TEMPLATES
        import questionary
        from prompt_toolkit.styles import Style

        style = Style.from_dict({
            "selected": "ansicyan bold",
            "highlighted": "ansicyan bold",
            "pointer": "ansicyan bold",
            "separator": "#666666",
            "instruction": "#555555",
        })

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
            style=style,
        ).ask()


def run() -> None:
    """运行角色管理."""
    while True:
        choice = ProfileMenuPage().run()

        if choice in ("back", "esc", None):
            break
        elif choice == "create":
            CreateProfilePage().run()
        elif choice and choice.startswith("view:"):
            player_id = choice.split(":", 1)[1]
            ProfileDetailPage(player_id).run()
