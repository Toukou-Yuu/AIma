"""角色管理 - 使用统一框架重构."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ui.interactive.framework import BACK, MenuPage, Page, Prompt, is_back
from ui.interactive.utils import (
    PLAYERS_DIR,
    create_profile,
    list_profiles,
)
from ui.terminal.components.character_card import render_character_card

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
            questionary.Choice("为角色添加 ASCII 形象", value="add_ascii"),
        ])
        return choices


class ProfileDetailPage(Page):
    """角色详情页（精美卡片式）。"""

    border_style = "bright_magenta"

    def __init__(self, player_id: str):
        self.player_id = player_id
        # 不设 title，由 character_card 完全负责显示

    def _render_content(self) -> None:
        # 使用精美卡片渲染
        card = render_character_card(self.player_id, PLAYERS_DIR)
        console.print(card)
        Prompt.press_any_key()


class CreateProfilePage(Page):
    """创建角色页."""

    title = "创建新角色"
    border_style = "bright_green"

    def _render_content(self) -> None:
        from .utils import PERSONA_TEMPLATES

        # 步骤 1: ID
        player_id = Prompt.text("角色标识 (用于文件夹名，如: ichihime_v2):")
        if is_back(player_id):
            return BACK
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
        if is_back(name):
            return BACK

        # 步骤 3: 选择模板
        template_choice = self._select_template()
        if is_back(template_choice):
            return BACK

        # 步骤 4: 是否自定义 prompt
        default_persona = PERSONA_TEMPLATES[template_choice]["persona"]
        customize = Prompt.confirm(
            f"是否自定义人格描述? (默认: {default_persona[:30]}...)",
            default=False,
        )
        if is_back(customize):
            return BACK

        custom_persona = None
        if customize:
            custom_persona = Prompt.multiline("输入自定义人格描述:")
            if is_back(custom_persona):
                return BACK

        # 创建
        try:
            path = create_profile(player_id, name, template_choice, custom_persona)
            console.print(f"[green]✓ 角色 '{name}' 已创建![/green]")
            console.print(f"  [dim]{path}[/dim]")
        except Exception as e:
            console.print(f"[red]创建失败: {e}[/red]")

        Prompt.press_any_key()

    def _select_template(self) -> str | object:
        """选择人格模板."""
        import questionary

        from .utils import PERSONA_TEMPLATES

        return Prompt.select(
            "",
            choices=[
                questionary.Choice(PERSONA_TEMPLATES['aggressive']['name'], value="aggressive"),
                questionary.Choice(PERSONA_TEMPLATES['defensive']['name'], value="defensive"),
                questionary.Choice(PERSONA_TEMPLATES['balanced']['name'], value="balanced"),
                questionary.Choice(PERSONA_TEMPLATES['adaptive']['name'], value="adaptive"),
            ],
            instruction="[上下键选择，回车确认]",
        )


class AddAsciiPage(Page):
    """为角色添加 ASCII 形象页."""

    title = "添加 ASCII 形象"
    border_style = "bright_yellow"

    def _render_content(self) -> None:
        from scripts.ascii_converter import image_to_unicode_art_halfblock

        # 步骤 1: 选择角色
        profiles = list_profiles()
        if not profiles:
            console.print("[red]没有可用的角色[/red]")
            Prompt.press_any_key()
            return

        import questionary

        choices = [questionary.Choice(p['name'], value=p['id']) for p in profiles]
        player_id = Prompt.select(
            "选择角色:",
            choices=choices,
        )

        if is_back(player_id):
            return BACK

        # 步骤 2: 输入图片路径（清晰提示）
        console.print(f"\n[dim]当前目录: {Path.cwd()}[/dim]")
        console.print("[dim]示例: img.png 或 configs/players/kavi/kavi.png[/dim]")
        image_path_str = Prompt.text("图片路径:")
        if is_back(image_path_str):
            return BACK
        if not image_path_str:
            return

        image_path = Path(image_path_str)
        if not image_path.exists():
            console.print(f"[red]错误: 图片不存在[/red]")
            console.print(f"[dim]  检查路径: {image_path}[/dim]")
            Prompt.press_any_key()
            return

        # 步骤 3: 输入宽度
        width_str = Prompt.text("输出宽度 (字符数，默认60):", default="60")
        if is_back(width_str):
            return BACK
        try:
            width = int(width_str) if width_str else 60
        except ValueError:
            console.print("[red]错误: 宽度必须是数字[/red]")
            Prompt.press_any_key()
            return

        # 步骤 4: 生成
        output_path = PLAYERS_DIR / player_id / "ascii.txt"
        try:
            image_to_unicode_art_halfblock(image_path, output_path, width)
            console.print(f"[green]✓ ASCII 形象已添加[/green]")
            console.print(f"  [dim]角色: {player_id}[/dim]")
            console.print(f"  [dim]文件: {output_path}[/dim]")
        except Exception as e:
            console.print(f"[red]生成失败: {e}[/red]")

        Prompt.press_any_key()


def run() -> None:
    """运行角色管理."""
    while True:
        choice = ProfileMenuPage().run()

        if choice is None or is_back(choice):
            break
        elif choice == "create":
            CreateProfilePage().run()
        elif choice == "add_ascii":
            AddAsciiPage().run()
        elif choice and choice.startswith("view:"):
            player_id = choice.split(":", 1)[1]
            ProfileDetailPage(player_id).run()
