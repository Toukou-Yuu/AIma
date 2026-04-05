"""统一页面框架 - 所有菜单/页面继承此类."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from typing import Any

console = Console()


class Page(ABC):
    """页面基类 - 统一处理清屏、异常捕获、UI渲染."""

    # 页面标题，子类可覆盖
    title: str = ""
    # 边框颜色
    border_style: str = "bright_cyan"

    def run(self) -> Any:
        """运行页面，自动处理清屏和异常."""
        self._clear_screen()
        self._render_header()

        try:
            return self._render_content()
        except KeyboardInterrupt:
            self._on_interrupt()
            return None
        except Exception as e:
            self._on_error(e)
            return None

    def _clear_screen(self) -> None:
        """清屏 - 使用系统命令减少闪烁."""
        import os
        import sys

        # Windows 使用 cls，其他使用 clear
        if sys.platform == "win32":
            os.system("cls")
        else:
            console.clear()

    def _render_header(self) -> None:
        """渲染页面标题."""
        from rich.align import Align
        from rich.panel import Panel
        from rich.text import Text

        if self.title:
            title = Text(self.title, style="bold bright_cyan")
            console.print()
            console.print(
                Panel(
                    Align.center(title),
                    border_style=self.border_style,
                    width=40,
                    padding=(0, 1),
                )
            )
            console.print()

    @abstractmethod
    def _render_content(self) -> Any:
        """子类实现：渲染页面内容."""
        ...

    def _on_interrupt(self) -> None:
        """处理中断（Ctrl+C）."""
        console.print("\n[dim]已取消[/dim]")

    def _on_error(self, error: Exception) -> None:
        """处理错误."""
        console.print(f"\n[red]错误: {error}[/red]")


class MenuPage(Page):
    """菜单页面基类 - 统一处理 questionary 菜单."""

    def _render_content(self) -> str | None:
        """渲染菜单."""
        import questionary
        from prompt_toolkit.styles import Style

        choices = self._get_choices()
        if not choices:
            return None

        style = Style.from_dict({
            "selected": "ansicyan bold",
            "highlighted": "ansicyan bold",
            "pointer": "ansicyan bold",
            "separator": "#666666",
            "question": "#444444",
            "instruction": "#555555",
        })

        return questionary.select(
            "",
            choices=choices,
            qmark="",
            pointer=">",
            instruction="[↑↓选择，回车确认]",
            style=style,
        ).ask()

    @abstractmethod
    def _get_choices(self) -> list:
        """子类实现：返回菜单选项."""
        ...


class Prompt:
    """统一输入提示类."""

    @staticmethod
    def confirm(message: str, default: bool = True) -> bool:
        """确认对话框."""
        import questionary
        from prompt_toolkit.styles import Style

        style = Style.from_dict({
            "question": "",
            "answer": "ansicyan bold",
        })
        return questionary.confirm(
            message,
            default=default,
            qmark="",
            style=style,
        ).ask() or False

    @staticmethod
    def text(message: str, default: str = "") -> str:
        """文本输入."""
        import questionary
        from prompt_toolkit.styles import Style
        style = Style.from_dict({"question": "", "answer": "ansicyan bold"})
        return questionary.text(message, default=default, qmark="", style=style).ask() or ""

    @staticmethod
    def number(message: str, default: str = "0") -> str:
        """数字输入."""
        import questionary
        from prompt_toolkit.styles import Style
        style = Style.from_dict({"question": "", "answer": "ansicyan bold"})
        return questionary.text(message, default=default, qmark="", style=style).ask() or default

    @staticmethod
    def multiline(message: str) -> str:
        """多行文本输入."""
        import questionary
        from prompt_toolkit.styles import Style
        style = Style.from_dict({"question": "", "answer": "ansicyan bold"})
        return questionary.text(message, multiline=True, qmark="", style=style).ask() or ""

    @staticmethod
    def press_any_key(message: str = "按任意键继续...") -> None:
        """按任意键继续."""
        import questionary
        console.print()
        console.print(f"[dim]{message}[/dim]")
        questionary.press_any_key_to_continue(message="").ask()
