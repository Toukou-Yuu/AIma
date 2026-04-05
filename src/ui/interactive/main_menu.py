"""主菜单 - 使用统一框架重构."""

from __future__ import annotations

from ui.interactive.framework import MenuPage, Page


class MainMenuPage(MenuPage):
    """主菜单."""

    title = "AIma 麻将 AI 终端"

    def _get_choices(self):
        import questionary
        return [
            questionary.Choice("demo演示", value="quick"),
            questionary.Choice("开始对局", value="match"),
            questionary.Choice("角色管理", value="profile"),
            questionary.Choice("牌谱回放", value="replay"),
            questionary.Separator(),
            questionary.Choice("退出", value="quit"),
        ]


def show_main_menu() -> str:
    """显示主菜单."""
    result = MainMenuPage().run()
    return result or "quit"
