"""主菜单 - 使用统一框架重构."""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from ui.interactive.framework import MenuPage, Page, is_back

console = Console()


def _get_model_info() -> str:
    """获取当前模型配置信息."""
    config_path = Path("configs/aima_kernel.yaml")
    if not config_path.exists():
        return "未配置"

    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        llm_cfg = cfg.get("llm", {})
        model = llm_cfg.get("model", "default")
        base_url = llm_cfg.get("base_url", "")

        # 判断是否为本地模型
        if "localhost" in base_url or "127.0.0.1" in base_url:
            location = "本地"
        elif "openai.com" in base_url:
            location = "OpenAI"
        elif "deepseek" in base_url:
            location = "DeepSeek"
        else:
            location = "远程"

        return f"{location}: {model}"
    except Exception:
        return "配置读取失败"


class MainMenuPage(MenuPage):
    """主菜单."""

    title = "AIma 麻将 AI 终端"
    allow_back = False

    def _render_header(self) -> None:
        """重写标题渲染，添加模型信息."""
        from rich.align import Align
        from rich.panel import Panel
        from rich.text import Text

        if self.title:
            title = Text(self.title, style="bold bright_cyan")
            model_info = _get_model_info()

            console.print()
            console.print(
                Panel(
                    Align.center(title),
                    border_style=self.border_style,
                    width=40,
                    padding=(0, 1),
                )
            )
            # 显示模型信息
            if model_info:
                console.print(
                    Align.center(f"[dim]{model_info}[/dim]"),
                    width=40,
                )
            console.print()

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
    if is_back(result):
        return "quit"
    return result or "quit"
