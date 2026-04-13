"""统一页面框架 - 所有菜单/页面继承此类."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from typing import Any

console = Console()


class NavigationAction(Enum):
    """统一页面导航动作."""

    BACK = "back"


BACK = NavigationAction.BACK


def is_back(value: object) -> bool:
    """判断返回值是否为统一的返回动作."""
    return value is BACK


class Page(ABC):
    """页面基类 - 统一处理清屏、异常捕获、UI渲染."""

    # 页面标题，子类可覆盖
    title: str = ""
    # 边框颜色
    border_style: str = "bright_cyan"
    # 当前页面是否支持返回上一层
    allow_back: bool = True

    def run(self) -> Any:
        """运行页面，自动处理清屏和异常."""
        self._clear_screen()
        self._render_header()

        try:
            return self._render_content()
        except KeyboardInterrupt:
            return self._on_interrupt()
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

    def _on_interrupt(self) -> NavigationAction | None:
        """处理中断（Ctrl+C）."""
        if self.allow_back:
            console.print("\n[dim]已返回上一层[/dim]")
            return BACK

        console.print("\n[dim]已取消[/dim]")
        return None

    def _on_error(self, error: Exception) -> None:
        """处理错误."""
        console.print(f"\n[red]错误: {error}[/red]")


class MenuPage(Page):
    """菜单页面基类 - 统一处理 questionary 菜单."""

    back_label: str = "返回上一层"

    def _render_content(self) -> str | NavigationAction | None:
        """渲染菜单."""
        import questionary
        from prompt_toolkit.styles import Style

        choices = list(self._get_choices())
        if not choices:
            return None

        if self.allow_back:
            choices.extend([
                questionary.Separator(),
                questionary.Choice(self.back_label, value=BACK),
            ])

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
            instruction=self._get_instruction(),
            style=style,
        ).ask() or BACK

    def _get_instruction(self) -> str:
        """菜单操作提示."""
        if self.allow_back:
            return "[↑↓选择，回车确认，Esc返回]"
        return "[↑↓选择，回车确认]"

    @abstractmethod
    def _get_choices(self) -> list:
        """子类实现：返回菜单选项."""
        ...


class Prompt:
    """统一输入提示类."""

    @staticmethod
    def _style():
        from prompt_toolkit.styles import Style

        return Style.from_dict({
            "question": "",
            "answer": "ansicyan bold",
            "selected": "ansicyan bold",
            "highlighted": "ansicyan bold",
            "pointer": "ansicyan bold",
            "separator": "#666666",
            "instruction": "#555555",
        })

    @staticmethod
    def _build_message(message: str, instruction: str | None = None) -> list[tuple[str, str]]:
        """构建统一的输入提示文本."""
        tokens: list[tuple[str, str]] = [("class:question", f"{message} ")]
        if instruction:
            tokens.append(("class:instruction", f"{instruction}"))
        return tokens

    @staticmethod
    def _read_text(
        message: str,
        default: str = "",
        *,
        multiline: bool = False,
        instruction: str | None = None,
    ) -> str | NavigationAction:
        """读取文本输入，并由框架统一处理返回导航."""
        from prompt_toolkit import PromptSession
        from prompt_toolkit.key_binding import KeyBindings

        bindings = KeyBindings()

        @bindings.add("escape")
        def _go_back(event) -> None:
            event.app.exit(result=BACK)

        if multiline:
            @bindings.add("c-s")
            def _submit(event) -> None:
                event.app.current_buffer.validate_and_handle()

        session = PromptSession(
            style=Prompt._style(),
            multiline=multiline,
            key_bindings=bindings,
        )
        answer = session.prompt(
            Prompt._build_message(message, instruction),
            default=default,
        )
        return BACK if answer is BACK else answer

    @staticmethod
    def select(
        message: str,
        choices: list,
        instruction: str = "[↑↓选择，回车确认，Esc返回]",
        allow_back: bool = True,
    ) -> Any:
        """统一选择输入."""
        import questionary

        resolved_choices = list(choices)
        if allow_back:
            resolved_choices.extend([
                questionary.Separator(),
                questionary.Choice("返回上一层", value=BACK),
            ])

        answer = questionary.select(
            message,
            choices=resolved_choices,
            qmark="",
            pointer=">",
            instruction=instruction,
            style=Prompt._style(),
        ).ask()
        return BACK if answer is None else answer

    @staticmethod
    def confirm(message: str, default: bool = True) -> bool | NavigationAction:
        """确认对话框."""
        import questionary

        choices = [
            questionary.Choice("是", value=True),
            questionary.Choice("否", value=False),
        ]
        if not default:
            choices.reverse()

        answer = Prompt.select(
            message,
            choices=choices,
            instruction="[↑↓选择，回车确认，Esc返回]",
        )
        return answer

    @staticmethod
    def text(message: str, default: str = "") -> str | NavigationAction:
        """文本输入."""
        return Prompt._read_text(message, default=default, instruction="(Esc返回)")

    @staticmethod
    def number(message: str, default: str = "0") -> str | NavigationAction:
        """数字输入."""
        answer = Prompt._read_text(message, default=default, instruction="(Esc返回)")
        return BACK if answer is BACK else (answer or default)

    @staticmethod
    def multiline(message: str) -> str | NavigationAction:
        """多行文本输入."""
        return Prompt._read_text(
            message,
            multiline=True,
            instruction="(Ctrl+S确认，Esc返回)",
        )

    @staticmethod
    def press_any_key(message: str = "按任意键继续...") -> None:
        """按任意键继续."""
        import questionary
        console.print()
        console.print(f"[dim]{message}[/dim]")
        questionary.press_any_key_to_continue(message="").ask()
